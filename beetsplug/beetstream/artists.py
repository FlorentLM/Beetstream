from beetsplug.beetstream.utils import *
from beetsplug.beetstream import app
import time
from collections import defaultdict
import flask


def artist_payload(artist_id: str) -> dict:

    artist_name = artist_id_to_name(artist_id).replace("'", "\\'")

    albums = flask.g.lib.albums(artist_name)
    albums = filter(lambda a: a.albumartist == artist_name, albums)

    payload = {
        "artist": {
            "id": artist_id,
            "name": artist_name,
            "child": list(map(map_album, albums))
        }
    }
    return payload

@app.route('/rest/getArtists', methods=["GET", "POST"])
@app.route('/rest/getArtists.view', methods=["GET", "POST"])
def get_artists():
    return _artists("artists")

@app.route('/rest/getIndexes', methods=["GET", "POST"])
@app.route('/rest/getIndexes.view', methods=["GET", "POST"])
def get_indexes():
    return _artists("indexes")

def _artists(version: str):
    r = flask.request.values

    with flask.g.lib.transaction() as tx:
        rows = tx.query("SELECT DISTINCT albumartist FROM albums")

    alphanum_dict = defaultdict(list)
    for row in rows:
        if row[0]:
            alphanum_dict[strip_accents(row[0][0]).upper()].append(row[0])

    payload = {
        version: {
            "ignoredArticles": "",
            "lastModified": int(time.time() * 1000),
            "index": [
                {"name": char, "artist": list(map(map_artist, artists))}
                for char, artists in sorted(alphanum_dict.items())
            ]
        }
    }
    return subsonic_response(payload, r.get('f', 'xml'))

@app.route('/rest/getArtist', methods=["GET", "POST"])
@app.route('/rest/getArtist.view', methods=["GET", "POST"])
def get_artist():
    r = flask.request.values

    artist_id = r.get('id')
    payload = artist_payload(artist_id)

    return subsonic_response(payload, r.get('f', 'xml'))

@app.route('/rest/getArtistInfo2', methods=["GET", "POST"])
@app.route('/rest/getArtistInfo2.view', methods=["GET", "POST"])
def artistInfo2():
    # TODO

    r = flask.request.values

    artist_name = artist_id_to_name(r.get('id'))

    payload = {
        "artistInfo2": {
            "biography": f"wow. much artist. very {artist_name}",
            "musicBrainzId": "",
            "lastFmUrl": "",
            "smallImageUrl": "",
            "mediumImageUrl": "",
            "largeImageUrl": ""
        }
    }

    return subsonic_response(payload, r.get('f', 'xml'))