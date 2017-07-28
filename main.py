# -*- coding: utf-8 -*-

import spotipy
import sys
import secrets
import datetime
import re
import operator
import codecs
import os
import spotipy.util as util
import spotipy.client as client

# developing on windows sucks!
from Crypto.Cipher import DES

class SpotifyManager(object):
    with open("../cipherkey") as f:
        cipherkey = f.read()

    des_obj = DES.new(cipherkey, DES.MODE_ECB)

    CLIENT_ID = des_obj.decrypt(secrets.CLIENT_ID).strip("!")
    CLIENT_SECRET = des_obj.decrypt(secrets.CLIENT_SECRET).strip("!")
    REDIRECT_URI = des_obj.decrypt(secrets.REDIRECT_URI).strip("!")
    USERNAME = des_obj.decrypt(secrets.USERNAME).strip("!")
    SCOPE = "playlist-read-private playlist-read-collaborative playlist-modify-public playlist-modify-private user-library-read"

    def __init__(self):
        self.playlist_id_to_tracks = dict()
        self.track_uri_to_playlist_ids = dict()
        self.track_uri_to_track = dict()

        token = util.prompt_for_user_token(
            username=self.USERNAME,
            scope=self.SCOPE,
            client_id=self.CLIENT_ID,
            client_secret=self.CLIENT_SECRET,
            redirect_uri=self.REDIRECT_URI
        )

        if token:
            self.token = token
            self.spotify = client.Spotify(auth=self.token)
        else:
            raise ValueError("Can't get token for {}".format(self.USERNAME))

    def get_playlist_tracks_from_spotify(self, playlist):
        """
        Downloads the tracks from spotify using api
        """
        pl_id = self.get_playlist_id(playlist)
        tracks = self.spotify.user_playlist_tracks(self.USERNAME, playlist_id=pl_id)
        output = []
        for t in tracks["items"]:
            if t == "None" or not t:
                continue
            t_uri = t["track"]["uri"]
            try:
                self.track_uri_to_playlist_ids[t_uri]
            except KeyError:
                self.track_uri_to_playlist_ids[t_uri] = set()
            
            self.track_uri_to_track[t_uri] = (t["track"]["name"], t)

            self.track_uri_to_playlist_ids[t_uri].add(pl_id)
            output.append(t)
        return output

    def get_my_tracks_from_playlist(self, playlist, update=False):
        """
        If tracks of playlist are already in memory, return that.
        If not, then store it to memeory and return it.
        """
        pl_id = self.get_playlist_id(playlist)

        try:
            tracks = self.playlist_id_to_tracks[pl_id]
        except (AttributeError, ValueError, KeyError):
            tracks = self.get_playlist_tracks_from_spotify(playlist)
            self.playlist_id_to_tracks[pl_id] = tracks

        return tracks

    def get_my_tracks_from_my_playlists(self, update=False):
        """
        Returns all tracks from my playlists.
        """
        output = []

        my_playlists = self.get_my_playlists()
        for pl in my_playlists:
            tracks = self.get_my_tracks_from_playlist(pl)
            for t in tracks:
                output.append(t)

        return output

    def get_id_from_uri(self, ri):
        pl_uri = ri
        uri_elems = pl_uri.split(":")
        pl_id = uri_elems[-1]

        return pl_id

    def get_playlist_id(self, playlist):
        """
        Gets playlist id from a given playlist object.
        """
        pl = playlist
        pl_uri = pl["uri"]
        uri_elems = pl_uri.split(":")
        pl_id = uri_elems[-1]

        return pl_id

    def get_my_playlists(self, update=False):
        """
        looks through my saved playlists and returns the ones owned by me.
        """
        output = []

        # only make the api request if update flag is passed in or
        # the variable isn't set.
        if update:
            playlists = self.spotify.user_playlists(self.USERNAME)
        else:
            try:
                output = self.playlists
            except AttributeError:
                playlists = self.spotify.user_playlists(self.USERNAME)
                update = True

        if update:
            for pl in playlists["items"]:
                if pl["owner"]["id"] == self.USERNAME:
                    output.append(pl)
            self.playlists = output

        return output

    def write_line(self, outfile, writestr):
        writestr += "\n"
        outfile.write(writestr)
        outfile.flush()
        os.fsync(outfile.fileno())

    def write_playlist_info(self, outfile, playlists, element):
        """
        literally retrieves an info from playlist jsons and writes a line.
        """
        writestr = ""
        for pl in playlists:
            if element == "id":
                pl_elem = self.get_playlist_id(pl)
            else:
                pl_elem = pl[element]
            writestr += '"{}",'.format(pl_elem.strip('"'))

        self.write_line(outfile, writestr)

    def write_playlist_infos(self, outfile, playlists):
        """
        just a wrapper function to write this.
        """
        self.write_playlist_info(outfile, playlists, "name")
        self.write_playlist_info(outfile, playlists, "uri")
        self.write_playlist_info(outfile, playlists, "id")

    def make_csv(self):
        """
        generates a local csv with my spotify playlists.
        """
        my_playlists = self.get_my_playlists()
        cur_date = datetime.datetime.now()
        date_str = re.sub(r"[ \-\:\.]", "", str(cur_date))[:13]
        outfile = codecs.open("songlist" + date_str + ".csv", "w", "utf-8")

        self.write_playlist_infos(outfile, my_playlists)
        self.get_my_tracks_from_my_playlists()

        pl_id_to_index = dict()
        for k in range(len(my_playlists)):
            pl_id_to_index[self.get_playlist_id(my_playlists[k])] = k

        sorted_songs = sorted(self.track_uri_to_track.iteritems(), key=lambda k : k[1][0] )
        for t_uri, (name, track) in sorted_songs:
            pl_ids = self.track_uri_to_playlist_ids[t_uri]
            indeces = []
            writestr = ""
            for pl_id in pl_ids:
                indeces.append(pl_id_to_index[pl_id])

            tot = len(my_playlists)
            while tot > 0:
                for k in range(len(indeces)):
                    write = True if indeces[k] == 0 else False
                    indeces[k] -= 1
                if write:
                    writestr += '"{}",'.format("x")
                else:
                    writestr += ','
                tot -= 1

            writestr += u'"{}",'.format(name)
            writestr += u'"{}",'.format(t_uri)
            self.write_line(outfile, writestr)
        
        outfile.close()

    def update_spotify(self):
        """
        Updates spotify playlists from local csv.
        """
        pass