from beetsplug.beetstream import ALB_ID_PREF, ART_ID_PREF, SNG_ID_PREF
import unicodedata
from datetime import datetime
from typing import Union
import beets
import subprocess
import platform
import flask
import json
import base64
import mimetypes
import os
import re
import posixpath
import xml.etree.cElementTree as ET
from math import ceil
from xml.dom import minidom

DEFAULT_MIME_TYPE = 'application/octet-stream'
EXTENSION_TO_MIME_TYPE_FALLBACK = {
    '.aac'  : 'audio/aac',
    '.flac' : 'audio/flac',
    '.mp3'  : 'audio/mpeg',
    '.mp4'  : 'audio/mp4',
    '.m4a'  : 'audio/mp4',
    '.ogg'  : 'audio/ogg',
    '.opus' : 'audio/opus',
}

def strip_accents(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')

def timestamp_to_iso(timestamp):
    return datetime.fromtimestamp(int(timestamp)).isoformat()

def is_json(res_format):
    return res_format == 'json' or res_format == 'jsonp'


def dict_to_xml(tag, d):
    """ Recursively converts a json-like dict to an XML tree """
    elem = ET.Element(tag)
    if isinstance(d, dict):
        for key, val in d.items():
            if isinstance(val, (dict, list)):
                child = dict_to_xml(key, val)
                elem.append(child)
            else:
                child = ET.Element(key)
                child.text = str(val)
                elem.append(child)
    elif isinstance(d, list):
        for item in d:
            child = dict_to_xml(tag, item)
            elem.append(child)
    else:
        elem.text = str(d)
    return elem

def subsonic_response(d: dict = {}, format: str = 'xml', failed=False):
    """ Wrap any json-like dict with the subsonic response elements
     and output the appropriate 'format' (json or xml) """

    STATUS = 'failed' if failed else 'ok'
    VERSION = '1.16.1'

    if format == 'json' or format == 'jsonp':
        wrapped = {
            'subsonic-response': {
                'status': STATUS,
                'version': VERSION,
                'type': 'Beetstream',
                'serverVersion': '1.4.5',
                'openSubsonic': True,
                **d
            }
        }
        return jsonpify(flask.request, wrapped)

    else:
        root = dict_to_xml("subsonic-response", d)
        root.set("xmlns", "http://subsonic.org/restapi")
        root.set("status", STATUS)
        root.set("version", VERSION)
        root.set("type", 'Beetstream')
        root.set("serverVersion", '1.4.5')
        root.set("openSubsonic", 'true')

        return flask.Response(xml_to_string(root), mimetype="text/xml")

def wrap_res(key, json):
    return {
        "subsonic-response": {
            "status": "ok",
            "version": "1.16.1",
            key: json
        }
    }

def jsonpify(request, data):
    if request.values.get("f") == "jsonp":
        callback = request.values.get("callback")
        return f"{callback}({json.dumps(data)});"
    else:
        return flask.jsonify(data)

def get_xml_root():
    root = ET.Element('subsonic-response')
    root.set('xmlns', 'http://subsonic.org/restapi')
    root.set('status', 'ok')
    root.set('version', '1.16.1')
    return root

def xml_to_string(xml):
    # Add declaration: <?xml version="1.0" encoding="UTF-8"?>
    return minidom.parseString(ET.tostring(xml, encoding='unicode', method='xml', xml_declaration=True)).toprettyxml()

def map_album(album):
    album = dict(album)
    return {
        "id": album_beetid_to_subid(str(album["id"])),
        "name": album["album"],
        "title": album["album"],
        "album": album["album"],
        "artist": album["albumartist"],
        "artistId": artist_name_to_id(album["albumartist"]),
        "parent": artist_name_to_id(album["albumartist"]),
        "isDir": True,
        "coverArt": album_beetid_to_subid(str(album["id"])) or "",
        "songCount": 1, # TODO
        "duration": 1, # TODO
        "playCount": 1, # TODO
        "created": timestamp_to_iso(album["added"]),
        "year": album["year"],
        "genre": album["genre"],
        "starred": "1970-01-01T00:00:00.000Z", # TODO
        "averageRating": 0 # TODO
    }

def map_album_xml(xml, album):
    album = dict(album)
    xml.set("id", album_beetid_to_subid(str(album["id"])))
    xml.set("name", album["album"])
    xml.set("title", album["album"])
    xml.set("album", album["album"])
    xml.set("artist", album["albumartist"])
    xml.set("artistId", artist_name_to_id(album["albumartist"]))
    xml.set("parent", artist_name_to_id(album["albumartist"]))
    xml.set("isDir", "true")
    xml.set("coverArt", album_beetid_to_subid(str(album["id"])) or "")
    xml.set("songCount", str(1)) # TODO
    xml.set("duration", str(1)) # TODO
    xml.set("playCount", str(1)) # TODO
    xml.set("created", timestamp_to_iso(album["added"]))
    xml.set("year", str(album["year"]))
    xml.set("genre", album["genre"])
    xml.set("starred", "1970-01-01T00:00:00.000Z") # TODO
    xml.set("averageRating", "0") # TODO

def map_album_list(album):
    album = dict(album)
    return {
        "id": album_beetid_to_subid(str(album["id"])),
        "parent": artist_name_to_id(album["albumartist"]),
        "isDir": True,
        "title": album["album"],
        "album": album["album"],
        "artist": album["albumartist"],
        "year": album["year"],
        "genre": album["genre"],
        "coverArt": album_beetid_to_subid(str(album["id"])) or "",
        "userRating": 5, # TODO
        "averageRating": 5, # TODO
        "playCount": 1,  # TODO
        "created": timestamp_to_iso(album["added"]),
        "starred": ""
    }

def map_song(song):
    song = dict(song)
    path = song["path"].decode('utf-8')
    return {
        "id": song_beetid_to_subid(str(song["id"])),
        "parent": album_beetid_to_subid(str(song["album_id"])),
        "isDir": False,
        "title": song["title"],
        "name": song["title"],
        "album": song["album"],
        "artist": song["albumartist"],
        "track": song["track"],
        "year": song["year"],
        "genre": song["genre"],
        "coverArt": _cover_art_id(song),
        "size": os.path.getsize(path),
        "contentType": path_to_mimetype(path),
        "suffix": song["format"].lower(),
        "duration": ceil(song["length"]),
        "bitRate": ceil(song["bitrate"]/1000),
        "path": path,
        "playCount": 1, #TODO
        "created": timestamp_to_iso(song["added"]),
        # "starred": "2019-10-23T04:41:17.107Z",
        "albumId": album_beetid_to_subid(str(song["album_id"])),
        "artistId": artist_name_to_id(song["albumartist"]),
        "type": "music",
        "discNumber": song["disc"]
    }

def map_song_xml(xml, song):
    song = dict(song)
    path = song["path"].decode('utf-8')
    xml.set("id", song_beetid_to_subid(str(song["id"])))
    xml.set("parent", album_beetid_to_subid(str(song["album_id"])))
    xml.set("isDir", "false")
    xml.set("title", song["title"])
    xml.set("name", song["title"])
    xml.set("album", song["album"])
    xml.set("artist", song["albumartist"])
    xml.set("track", str(song["track"]))
    xml.set("year", str(song["year"]))
    xml.set("genre", song["genre"])
    xml.set("coverArt", _cover_art_id(song)),
    xml.set("size", str(os.path.getsize(path)))
    xml.set("contentType", path_to_mimetype(path))
    xml.set("suffix", song["format"].lower())
    xml.set("duration", str(ceil(song["length"])))
    xml.set("bitRate", str(ceil(song["bitrate"]/1000)))
    xml.set("path", path)
    xml.set("playCount", str(1)) #TODO
    xml.set("created", timestamp_to_iso(song["added"]))
    xml.set("albumId", album_beetid_to_subid(str(song["album_id"])))
    xml.set("artistId", artist_name_to_id(song["albumartist"]))
    xml.set("type", "music")
    if song["disc"]:
        xml.set("discNumber", str(song["disc"]))

def _cover_art_id(song):
    if song['album_id']:
        return album_beetid_to_subid(str(song['album_id']))
    return song_beetid_to_subid(str(song['id']))

def map_artist(artist_name):
    return {
        "id": artist_name_to_id(artist_name),
        "name": artist_name,
        # TODO
        # "starred": "2021-07-03T06:15:28.757Z", # nothing if not starred
        "coverArt": "",
        "albumCount": 1,
        "artistImageUrl": "https://t4.ftcdn.net/jpg/00/64/67/63/360_F_64676383_LdbmhiNM6Ypzb3FM4PPuFP9rHe7ri8Ju.jpg"
    }

def map_artist_xml(xml, artist_name):
    xml.set("id", artist_name_to_id(artist_name))
    xml.set("name", artist_name)
    xml.set("coverArt", "")
    xml.set("albumCount", "1")
    xml.set("artistImageUrl", "https://t4.ftcdn.net/jpg/00/64/67/63/360_F_64676383_LdbmhiNM6Ypzb3FM4PPuFP9rHe7ri8Ju.jpg")

def map_playlist(playlist):
    return {
        'id': playlist.id,
        'name': playlist.name,
        'songCount': len(playlist.songs),
        'duration': playlist.duration,
        'created': timestamp_to_iso(playlist.ctime),
        'changed': timestamp_to_iso(playlist.mtime),
        # 'owner': 'userA',     # TODO
        # 'public': True,
    }

def artist_name_to_id(artist_name: str):
    base64_name = base64.urlsafe_b64encode(artist_name.encode('utf-8')).decode('utf-8')
    return f"{ART_ID_PREF}{base64_name}"

def artist_id_to_name(artist_id: str):
    base64_id = artist_id[len(ART_ID_PREF):]
    return base64.urlsafe_b64decode(base64_id.encode('utf-8')).decode('utf-8')

def album_beetid_to_subid(album_id: str):
    return ALB_ID_PREF + album_id

def album_subid_to_beetid(album_id: str):
    return album_id[len(ALB_ID_PREF):]

def song_beetid_to_subid(song_id: str):
    return SNG_ID_PREF + song_id

def song_subid_to_beetid(song_id: str):
    return song_id[len(SNG_ID_PREF):]

def path_to_mimetype(path):
    result = mimetypes.guess_type(path)[0]

    if result:
        return result

    # our mimetype database didn't have information about this file extension.
    base, ext = posixpath.splitext(path)
    result = EXTENSION_TO_MIME_TYPE_FALLBACK.get(ext)

    if result:
        return result

    flask.current_app.logger.warning(f"No mime type mapped for {ext} extension: {path}")

    return DEFAULT_MIME_TYPE

def handleSizeAndOffset(collection, size, offset):
    if size is not None:
        if offset is not None:
            return collection[offset:offset + size]
        else:
            return collection[0:size]
    else:
        return collection

def genres_splitter(genres_string):
    delimiters = re.compile('|'.join([';', ',', '/', '\\|']))
    return [g.strip().title()
            .replace('Post ', 'Post-')
            .replace('Prog ', 'Prog-')
            .replace('.', ' ')
            for g in re.split(delimiters, genres_string)]


def creation_date(filepath):
    """ Get a file's creation date
        See: http://stackoverflow.com/a/39501288/1709587 """
    if platform.system() == 'Windows':
        return os.path.getctime(filepath)
    elif platform.system() == 'Darwin':
        stat = os.stat(filepath)
        return stat.st_birthtime
    else:
        stat = os.stat(filepath)
        try:
            # On some Unix systems, st_birthtime is available so try it
            return stat.st_birthtime
        except AttributeError:
            try:
                # Run stat twice because it's faster and easier than parsing the %W format...
                ret = subprocess.run(['stat', '--format=%W', filepath], stdout=subprocess.PIPE)
                timestamp = ret.stdout.decode('utf-8').strip()

                # ...but we still want millisecond precision :)
                ret = subprocess.run(['stat', '--format=%w', filepath], stdout=subprocess.PIPE)
                millis = ret.stdout.decode('utf-8').rsplit('.', 1)[1].split()[0].strip()

                return float(f'{timestamp}.{millis}')
            except:
                # If that did not work, settle for last modification time
                return stat.st_mtime