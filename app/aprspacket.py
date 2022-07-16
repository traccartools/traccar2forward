#!/usr/bin/env python

def aprspacket(sonde_data):
    #   credits:
    #   radiosonde_auto_rx - APRS Exporter
    #   Copyright (C) 2018  Mark Jessop <vk5qi@rfhead.net>
    #   Released under GNU GPL v3 or later
    #   https://github.com/projecthorus/radiosonde_auto_rx/blob/master/auto_rx/autorx/aprs.py/


    fromcall = sonde_data["fromcall"]
    tocall = sonde_data["tocall"]
    symbol_table = sonde_data["symbol_table"]
    symbol = sonde_data["symbol"]
    comment = sonde_data["comment"]


    # Convert float latitude to APRS format (DDMM.MM)
    lat = float(sonde_data["latitude"])
    lat_degree = abs(int(lat))
    lat_minute = abs(lat - int(lat)) * 60.0
    lat_min_str = ("%02.4f" % lat_minute).zfill(7)[:5]
    lat_dir = "S"
    if lat > 0.0:
        lat_dir = "N"
    lat_str = "%02d%s" % (lat_degree, lat_min_str) + lat_dir

    # Convert float longitude to APRS format (DDDMM.MM)
    lon = float(sonde_data["longitude"])
    lon_degree = abs(int(lon))
    lon_minute = abs(lon - int(lon)) * 60.0
    lon_min_str = ("%02.4f" % lon_minute).zfill(7)[:5]
    lon_dir = "E"
    if lon < 0.0:
        lon_dir = "W"
    lon_str = "%03d%s" % (lon_degree, lon_min_str) + lon_dir

    # Generate the added digits of precision, as per http://www.aprs.org/datum.txt
    # Base-91 can only encode decimal integers between 0 and 93 (otherwise we end up with non-printable characters)
    # So, we have to scale the range 00-99 down to 0-90, being careful to avoid errors due to floating point math.
    _lat_prec = int(round(float(("%02.4f" % lat_minute)[-2:]) / 1.10))
    _lon_prec = int(round(float(("%02.4f" % lon_minute)[-2:]) / 1.10))

    # Now we can add 33 to the 0-90 value to produce the Base-91 character.
    _lat_prec = chr(_lat_prec + 33)
    _lon_prec = chr(_lon_prec + 33)

    # Produce Datum + Added precision string
    # We currently assume all position data is using the WGS84 datum,
    _datum = "!w%s%s!" % (_lat_prec, _lon_prec)

    # Convert Alt (in metres) to feet
    if ("altitude" in sonde_data.keys()):
        alt = round(float(sonde_data["altitude"]) / 0.3048)
    else:
        alt = 0
    alt_str = "%06d" %  alt
    # Produce the timestamp
    _aprs_timestamp = sonde_data["fixTime"].strftime("%H%M%S")

    # Generate course/speed data. (Speed in knots)
    if ("course" in sonde_data.keys()) and ("speed" in sonde_data.keys()):
        course_speed = "%03d/%03d" % (
            int(sonde_data["course"]),
            round(sonde_data["speed"]),
            #round(sonde_data["speed"] / 1.852), # km/h to knots
        )
    else:
        course_speed = "000/000"

    out_str = f"{fromcall}>{tocall}:" + \
        f"/{_aprs_timestamp}h{lat_str}{symbol_table}{lon_str}{symbol}" + \
        f"{course_speed}/A={alt_str} {comment} {_datum}"

    return (out_str)



if __name__ == '__main__':
    from datetime import datetime
    import aprslib

    diz = {"latitude":43, "longitude":11, "altitude":100, "fixTime":datetime.now(), "course":60, "speed":70}
    dizusr = {"fromcall":"N0CALL-10", "tocall":"TRCCAR,TCPIP*", "symbol_table":"/", "symbol":"[", "comment":"test"}


    t = aprspacket({**diz, **dizusr})
    print("Test")
    print(t)
    print(aprslib.parse(t))

