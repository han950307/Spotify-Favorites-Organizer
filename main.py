# -*- coding: utf-8 -*-

import spotipy
import sys
import secrets
import datetime
import re
import operator
import csv
import codecs
import os
import shutil
import spotipy.util as util
import spotipy.client as client

# developing on windows sucks!
from Crypto.Cipher import DES

class SpotifyManager(object):
    # with open("../cipherkey") as f:
    #     cipherkey = f.read()

    # des_obj = DES.new(cipherkey, DES.MODE_ECB)

    # CLIENT_ID = des_obj.decrypt(secrets.CLIENT_ID).strip("!")
    # CLIENT_SECRET = des_obj.decrypt(secrets.CLIENT_SECRET).strip("!")
    # REDIRECT_URI = des_obj.decrypt(secrets.REDIRECT_URI).strip("!")
    # USERNAME = des_obj.decrypt(secrets.USERNAME).strip("!")

    CLIENT_ID = secrets.CLIENT_ID
    CLIENT_SECRET = secrets.CLIENT_SECRET
    REDIRECT_URI = secrets.REDIRECT_URI
    USERNAME = secrets.USERNAME

    DATA_FILENAME = "song_data.csv"

    SCOPE = "playlist-read-private playlist-read-collaborative playlist-modify-public playlist-modify-private user-library-read"

    def __init__(self):
        self.playlist_id_to_tracks = dict()
        self.track_uri_to_playlist_ids = dict()
        self.playlist_name_to_playlist_id = dict()
        self.playlist_id_to_playlist_name = dict()
        self.track_uri_to_track = dict()  # track_name, track object
        self.playlist_id_to_playlist = dict()
        self.playlists = []

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
        elif self.playlists:
            output = self.playlists
        else:
            playlists = self.spotify.user_playlists(self.USERNAME)
            update = True

        if update:
            for pl in playlists["items"]:
                if pl["owner"]["id"] == self.USERNAME:
                    output.append(pl)
                    pl_id = self.get_playlist_id(pl)
                    self.playlist_id_to_playlist[pl_id] = pl
                    self.playlist_id_to_playlist_name[pl_id] = pl["name"]
                    self.playlist_name_to_playlist_id[pl["name"]] = pl_id
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
        writestr = '"","",'
        for pl in playlists:
            if element == "id":
                pl_elem = self.get_playlist_id(pl)
            else:
                pl_elem = pl[element]
            writestr += '"{}",'.format(pl_elem.strip('"'))

        self.write_line(outfile, writestr)

    def get_data_from_spotify(self):
        """
        returns a list of dict track uri to playlist ids
        from spotify
        """
        self.get_my_playlists()
        self.get_my_tracks_from_my_playlists()
        return self.track_uri_to_playlist_ids

    def make_csv_from_spotify(self):
        track_uri_to_playlist_ids = self.get_data_from_spotify()
        return self.make_csv(track_uri_to_playlist_ids)

    def pull_data_from_spotify(self, readable=False):
        """
        generates a local csv with my spotify playlists.
        """
        my_playlists = self.get_my_playlists()
        cur_date = datetime.datetime.now()
        date_str = re.sub(r"[ \-\:\.]", "", str(cur_date))[:13]
        outfile_name = "songlist" + date_str + ".csv"
        outfile = codecs.open(outfile_name, "w", "utf-8")
        # If the file exists, make a backup.
        data_sheet_exists = True
        if not os.path.isfile(self.DATA_FILENAME):
            data_sheet_exists = False

        # different logic depending on whether datasheet exists.
        if not data_sheet_exists:
            data_outfile = codecs.open(self.DATA_FILENAME, "w", "utf-8")
        else:
            # make dict from datasheet.
            pass

        # self.write_playlist_info(outfile, playlists, "name")
        # self.write_playlist_info(outfile, playlists, "uri")
        # self.write_playlist_info(outfile, playlists, "id")

        if not data_sheet_exists:
            # self.write_playlist_info(data_outfile, playlists, "uri")
            pass

        self.get_my_tracks_from_my_playlists()

        for t_uri, (name, track) in self.track_uri_to_track:
            pl_ids = self.track_uri_to_playlist_ids[t_uri]
            indeces = set()
            writestr = ""

            writestr += u'"{}",'.format(name)
            writestr += u'"{}",'.format(t_uri)

            for pl_id in playlist_id_to_playlist.keys():
                for pl_id in pl_ids:
                    writestr += u'"{}",'.format(self.playlist_id_to_playlist[t_uri]["name"])
                else:
                    writestr += u'"",'

            self.write_line(outfile, writestr)

            if not data_sheet_exists:
                self.write_line(data_outfile, writestr)
        
        outfile.close()

        if not data_sheet_exists:
            data_outfile.close()

        self.update_local_data(outfile_name)

    def load_csv(self, csv_path):
        """
        Reads from csv and returns a dict containing
        track uri to playlist names
        """
        track_uri_to_playlist_ids = dict()
        first_row = True
        index_to_pl_name = dict()

        with codecs.open(csv_path, "r", "utf-8") as csvfile:
            reader = csv.reader(csvfile, delimiter=',')
            for row in reader:
                if first_row:
                    ind = 0
                    first_row = False
                    for elem in row:
                        index_to_pl_name[ind] = elem.strip('"')
                        ind += 1
                    continue
                t_uri = row[1].strip('"')
                t_playlist_ids = []
                for k in range(2, len(row)):
                    elem = row[k].strip('"')
                    if elem:
                        t_playlist_ids.append(self.playlist_name_to_playlist_id[index_to_pl_name[k]])
                track_uri_to_playlist_ids[t_uri] = t_playlist_ids

        return track_uri_to_playlist_ids

    def make_csv(self, data, outfile_name=None):
        """
        uses the given data to export to csv.
        expects a track_uri to playlist_id.
        returns outfile name
        """
        my_playlists = self.get_my_playlists()
        cur_date = datetime.datetime.now()
        date_str = re.sub(r"[ \-\:\.]", "", str(cur_date))[:13]
        if not outfile_name:
            outfile_name = "songlist" + date_str + ".csv"
        outfile = codecs.open(outfile_name, "w", "utf-8")
        # If the file exists, make a backup.
        data_sheet_exists = True

        self.write_playlist_info(outfile, my_playlists, "name")
        my_playlists = self.get_my_playlists()

        pl_id_to_index = dict()
        for k in range(len(my_playlists)):
            pl_id_to_index[self.get_playlist_id(my_playlists[k])] = k

        for t_uri, pl_ids in data.iteritems():
            indeces = []
            writestr = ""
            name = self.track_uri_to_track[t_uri][0]

            for pl_id in pl_ids:
                indeces.append(pl_id_to_index[pl_id])

            writestr += u'"{}",'.format(name)
            writestr += u'"{}",'.format(t_uri)

            tot = len(my_playlists)

            while tot > 0:
                for k in range(len(indeces)):
                    write = True if indeces[k] == 0 else False
                    indeces[k] -= 1
                if write:
                    writestr += '"{}",'.format("x")
                else:
                    writestr += '"",'
                tot -= 1

            self.write_line(outfile, writestr)
        
        outfile.close()
        return outfile_name

    def update_local_data(self, csv_path):
        """
        uses the given csv_path to update the local data sheet
        """
        track_uri_to_playlist_names = self.load_csv(csv_path)
        track_uri_to_playlist_names_local = self.load_csv(self.DATA_FILENAME)




    def update_spotify(self, csv_path):
        """
        Updates spotify playlists from local csv.
        """

        # cases
        # need to keep info even if added to old likes
        # - when pushing, if in old likes and in another
        #   remote playlist, remove from remote.
        # - when pushing, if not in old likes, then
        #   make sure remote is synced to local.
        # - when pushing, update data sheet with csv_path
        # - when i pull, if in old likes and in local data, use local data
        # - when i pull, if not in old likes, then update with spotify data
        cur_date = datetime.datetime.now()
        date_str = re.sub(r"[ \-\:\.]", "", str(cur_date))[:13]

        if os.path.isfile(self.DATA_FILENAME):
            shutil.copyfile(self.DATA_FILENAME, self.DATA_FILENAME.strip(".csv") + date_str + ".csv")
        else:
            raise ValueError("data sheet file not found. Please pull first.")

        pass
