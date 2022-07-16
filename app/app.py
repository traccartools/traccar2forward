#!/usr/bin/env python3

import logging
from operator import length_hint
import os
import signal

import aprslib
import requests
import validators
import string

import dateutil.parser as dp

from datetime import datetime
import json
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

import webdav4.client
from io import BytesIO
from aprspacket import aprspacket

DEFAULT_PORT = 8080
DEFAULT_APRS_HOST = 'rotate.aprs.net'
DEFAULT_APRS_PORT = 14580

LOGGER = logging.getLogger(__name__)

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    pass

class HTTPRequestHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length']) # <--- Gets the size of data
        post_data = self.rfile.read(content_length).decode('utf-8') # <--- Gets the data itself
        LOGGER.debug("POST request,\nPath: %s\nHeaders:\n%s\n\nBody:\n%s\n", str(self.path), str(self.headers), post_data)

        self.send_response(200)
        self.end_headers()
        self.wfile.write("POST request for {}".format(self.path).encode('utf-8'))

        T2F.process_data(post_data)

class Traccar2Forward():
    def __init__(self, conf: dict):
        # Initialize the class.
        super().__init__()

        self.port = conf.get("Port")
        self.JsonKeyword = conf.get("JsonKeyword")
        self.GetKeyword = conf.get("GetKeyword")
        self.PostKeyword = conf.get("PostKeyword")
        self.PhonetrackKeyword = conf.get("PhonetrackKeyword")
        self.PhonetrackHost = conf.get("PhonetrackHost")
        self.WebdavKeyword = conf.get("WebdavKeyword")
        self.AprsKeyword = conf.get("AprsKeyword")
        self.AprsHost = conf.get("AprsHost")
        self.AprsLocalKeyword = conf.get("AprsLocalKeyword")
        self.AprsLocalHost = conf.get("AprsLocalHost")

        self.keywords = list(filter(None, [self.JsonKeyword, self.GetKeyword, self.PostKeyword, self.PhonetrackKeyword, self.WebdavKeyword, self.AprsKeyword, self.AprsLocalKeyword]))


    def listen(self):
        server = ThreadingHTTPServer(('0.0.0.0', self.port), HTTPRequestHandler)
        LOGGER.info(f"Starting server at http://127.0.0.1:{self.port}")
        server.serve_forever()

    def read_testfile(self, filename):
        with open(filename) as f:
            self.process_data(f.read())

    def parsetodict(self, j):
        di = {}
        for k in ["name", "uniqueId", "status"]:
            di[k] = j["device"][k]

        for k in ["deviceId","protocol","valid","latitude","longitude","altitude","speed","course","accuracy"]:
            di[k] = j["position"][k]

        for k in ["deviceTime","fixTime"]:
            di[k] = dp.parse(j["position"][k])
        
        for k in ["ignition","motion"]:
            di[k] = j["position"]["attributes"][k]

        return(di)


    def http_send(self, url: str, dic: dict, post = False, j : json = None):
        ndic = dict(dic) # dictionary is passed by reference
        ndic["deviceTime"] = datetime.timestamp(ndic["deviceTime"])
        ndic["fixTime"] = datetime.timestamp(ndic["fixTime"])

        try:
            url = url.format(**ndic)
        except e:
            LOGGER.error(f"url format error: {str(e)}")
            return

        if not validators.url(url):
            LOGGER.debug(f"Invalid url ({url})")
            return

        try:
            if post:
                # if j:
                re = requests.post(url, json = j)
                # else:
                #     re = requests.post(url)
                LOGGER.debug(f"POST {re.status_code} {re.reason} - {re.content.decode()}")
            else:
                re = requests.get(url)
                LOGGER.debug(f"GET {re.status_code} {re.reason} - {re.content.decode()}")
            
            if re.status_code > 299:
                LOGGER.error(f"{re.status_code} {re.reason} - {re.content.decode()}")
        except requests.exceptions.ConnectionError as e:
            LOGGER.error(f"ConnectionError: {str(e)}")
            return
        except requests.exceptions.RequestException as e:
            LOGGER.error(f"RequestException: {str(e)}")
            return

    def aprs_send(self, conf: str, dic: dict, APRS_HOST: str = DEFAULT_APRS_HOST):
        vs = conf.strip().split(" ")
        
        APRS_CALLSIGN = vs[0]
        APRS_PASSCODE = vs[1]
        APRS_FROMCALL = vs[2]
        APRS_SYMBOL = vs[3]
        APRS_COMMENT = vs[4]

        dizusr = {"fromcall":APRS_FROMCALL, "tocall":"TRCCAR,TCPIP*", "symbol_table":APRS_SYMBOL[0], "symbol":APRS_SYMBOL[1], "comment":APRS_COMMENT}
        pr = aprspacket({**dic, **dizusr})

        LOGGER.debug(f"Aprs packet: {str(pr)}")

        try:
            #send position to APRS-IS
            APRSIS = aprslib.IS(APRS_CALLSIGN, host=APRS_HOST, passwd=APRS_PASSCODE, port=DEFAULT_APRS_PORT)
            APRSIS.connect()
            APRSIS.sendall(str(pr))
            APRSIS.close()
        except (aprslib.ConnectionError) as e:
            LOGGER.error(f"APRS ConnectionError: {str(e)}")
            pass
        except (aprslib.GenericError) as e:
            LOGGER.error(f"APRS GenericError: {str(e)}")
            pass




    def process_data(self, data):
        j = json.loads(data)
        # print(json.dumps(j, indent=2))

        attributes = j.get("device").get("attributes")
        if not attributes:
            return
        
        dizio = self.parsetodict(j)
        # print(dizio)

        for att, value in attributes.items():
            matches = [i for i in self.keywords if re.search("^" + i + "[0-9]{0,1}$", att.lower())]
            if not matches:
                continue
            
            # replace with match/case function in python 3.10
            attn = matches[0]

            #json
            if attn == self.JsonKeyword:
                LOGGER.debug(f"Attribute {att}")
                qry = value.strip()
                self.http_send(qry, dizio, True, j)

            #get
            elif attn == self.GetKeyword:
                LOGGER.debug(f"Attribute {att}")
                qry = value.strip()
                self.http_send(qry, dizio)

            #post
            elif attn == self.PostKeyword:
                LOGGER.debug(f"Attribute {att}")
                qry = value.strip()
                self.http_send(qry, dizio, True)
            
            #PhoneTrack
            elif attn == self.PhonetrackKeyword:
                LOGGER.debug(f"Attribute {att}")
                v = value.split("/")
                token = v[0]
                name = v[1] if len(v)>1 else j["device"]["name"]
            
                if not (set(token).issubset(string.hexdigits) and len(token) == 32): #checks the token
                    LOGGER.info(f"Invalid PhoneTrack token: {token}")
                    continue
                    
                qry = self.PhonetrackHost + "/apps/phonetrack/log/gpslogger/{token}/{name}?lat={latitude}&lon={longitude}&alt={altitude}&acc={accuracy}&speed={speed}&bearing={course}&timestamp={fixTime}"

                dtoken = {"token": token, "name": name}
                duniq = {**dizio, **dtoken}
                duniq["speed"] = duniq["speed"] / 1.944 # speed ftom knots to mph
                self.http_send(qry, duniq)

            #Webdav
            elif attn == self.WebdavKeyword:
                LOGGER.debug(f"Attribute {att}")
                vs = value.strip().split(" ")
                
                if len(vs) == 1 and "/s/" in vs[0]:
                    #it's a nextcloud share
                    ur, us = vs[0].split("/s/")
                    ur = ur + "/public.php/webdav/"
                    us = us.replace("/","")
                    up = ""
                else:
                    vs.append("")
                    ur, us, up = vs[:3]
                
                LOGGER.debug(f"Webdav: {ur} {us}")

                fol = dizio["uniqueId"] +"_"+ dizio["name"]
                ts = dizio["fixTime"]

                try:
                    client = webdav4.client.Client(ur, auth=(us, up))
                    if not client.exists(fol):
                        client.mkdir(fol)
                    fn = fol + "/" + datetime.strftime(ts,"%Y%m%d_%H%M%S") + ".json"
                    client.upload_fileobj(BytesIO(json.dumps(j, indent=2).encode('utf-8')), fn, True)

                except (webdav4.client.ClientError) as e:
                    LOGGER.error(f"Webdav error: {str(e)}")

            #aprs
            elif attn == self.AprsKeyword:
                LOGGER.debug(f"Attribute {att}")                
                self.aprs_send(value, dizio, self.AprsHost)

            #aprslocal
            elif attn == self.AprsLocalKeyword:
                LOGGER.debug(f"Attribute {att}")                
                self.aprs_send(value, dizio, self.AprsLocalHost)




if __name__ == '__main__':
    log_level = os.environ.get("LOG_LEVEL", "DEBUG")

    logging.basicConfig(level=log_level)


    def sig_handler(sig_num, frame):
        logging.debug(f"Caught signal {sig_num}: {frame}")
        logging.info("Exiting program.")
        exit(0)

    signal.signal(signal.SIGTERM, sig_handler)
    signal.signal(signal.SIGINT, sig_handler)
    
    config = {}
    config["Port"] = os.environ.get("PORT", DEFAULT_PORT)
    config["JsonKeyword"] = os.environ.get("JSON_KEYWORD")
    config["GetKeyword"] = os.environ.get("GET_KEYWORD")
    config["PostKeyword"] = os.environ.get("POST_KEYWORD")
    config["PhonetrackKeyword"] = os.environ.get("PHONETRACK_KEYWORD")
    config["PhonetrackHost"] = os.environ.get("PHONETRACK_HOST")
    config["WebdavKeyword"] = os.environ.get("WEBDAV_KEYWORD")
    config["AprsKeyword"] = os.environ.get("APRS_KEYWORD")
    config["AprsHost"] = os.environ.get("APRS_HOST")
    config["AprsLocalKeyword"] = os.environ.get("APRSLOCAL_KEYWORD")
    config["AprsLocalHost"] = os.environ.get("APRSLOCAL_HOST")

    T2F = Traccar2Forward(config)
    # T2F.read_testfile('SamplePost.json')
    T2F.listen()
    


