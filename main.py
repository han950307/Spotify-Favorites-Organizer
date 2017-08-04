# -*- coding: utf-8 -*-

import spotipy
import sys
import secrets
import datetime
import re
import unicodecsv
import operator
import csv
import codecs
import os
import shutil
import spotipy.util as util
import spotipy.client as client

# developing on windows sucks!
from Crypto.Cipher import DES
import cStringIO


reload(sys)
sys.setdefaultencoding("utf-8")


class UTF8Recoder:

    def __init__(self, f, encoding):
        self.reader = codecs.getreader(encoding)(f)

    def __iter__(self):
        return self

    def next(self):
        return self.reader.next().encode("utf-8")


class UnicodeReader:

    def __init__(self, f, dialect=csv.excel, encoding="utf-8-sig", **kwds):
        f = UTF8Recoder(f, encoding)
        self.reader = csv.reader(f, dialect=dialect, **kwds)

    def next(self):
        '''next() -> unicode
        This function reads and returns the next line as a Unicode string.
        '''
        row = self.reader.next()
        return [unicode(s, "utf-8") for s in row]

    def __iter__(self):
        return self


class UnicodeWriter:

    def __init__(self, f, dialect=csv.excel, encoding="utf-8-sig", **kwds):
        self.queue = cStringIO.StringIO()
        self.writer = csv.writer(self.queue, dialect=dialect, **kwds)
        self.stream = f
        self.encoder = codecs.getincrementalencoder(encoding)()

    def writerow(self, row):
        '''writerow(unicode) -> None
        This function takes a Unicode string and encodes it to the output.
        '''
        self.writer.writerow([s.encode("utf-8") for s in row])
        data = self.queue.getvalue()
        data = data.decode("utf-8")
        data = self.encoder.encode(data)
        self.stream.write(data)
        self.queue.truncate(0)

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)


class SpotifyManager(object):
    with open("../cipherkey") as f:
        cipherkey = f.read()

    des_obj = DES.new(cipherkey, DES.MODE_ECB)

    CLIENT_ID = des_obj.decrypt(secrets.CLIENT_ID).strip("!")
    CLIENT_SECRET = des_obj.decrypt(secrets.CLIENT_SECRET).strip("!")
    REDIRECT_URI = des_obj.decrypt(secrets.REDIRECT_URI).strip("!")
    USERNAME = des_obj.decrypt(secrets.USERNAME).strip("!")

    OLD_LIKES_NAMES = ["Old Likes", "Old KPOP"]
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

    def unicode_csv_reader(utf8_data, dialect=csv.excel, **kwargs):
        csv_reader = csv.reader(utf8_data, dialect=dialect, **kwargs)
        for row in csv_reader:
            yield [unicode(cell, 'utf-8') for cell in row]

    def get_playlist_tracks_from_spotify(self, playlist, update=False):
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

            if update:
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
            tracks = self.get_playlist_tracks_from_spotify(playlist, update)
            self.playlist_id_to_tracks[pl_id] = tracks
            update = False
        if update:
            tracks = self.get_playlist_tracks_from_spotify(playlist, update)
            self.playlist_id_to_tracks[pl_id] = tracks

        return tracks

    def get_my_tracks_from_my_playlists(self, update=False):
        """
        Returns all tracks from my playlists.
        """
        output = []

        my_playlists = self.get_my_playlists(update)
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
            self.playlists = []
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
        writestr = '"Song Name","Song URI",'
        for pl in playlists:
            if element == "id":
                pl_elem = self.get_playlist_id(pl)
            else:
                pl_elem = pl[element]
            writestr += '"{}",'.format(pl_elem.strip('"'))

        self.write_line(outfile, writestr)

    def get_data_from_spotify(self, update=True):
        """
        returns a list of dict track uri to playlist ids
        from spotify
        """
        self.get_my_playlists(update=update)
        self.get_my_tracks_from_my_playlists(update=update)
        return self.track_uri_to_playlist_ids

    def make_csv_from_spotify(self):
        track_uri_to_playlist_ids = self.get_data_from_spotify(update=True)
        if not os.path.isfile(self.DATA_FILENAME):
            self.make_csv(track_uri_to_playlist_ids, self.DATA_FILENAME)
        csv_path = self.make_csv(track_uri_to_playlist_ids)
        self.update_local_data(csv_path)
        return csv_path

    def load_csv(self, csv_path):
        """
        Reads from csv and returns a dict containing
        track uri to playlist ids
        """
        track_uri_to_playlist_ids = dict()
        first_row = True
        index_to_pl_name = dict()

        reader = UnicodeReader(open(csv_path, "rb"))
        for row in reader:
            if not row:
                continue
            if first_row:
                ind = 0
                first_row = False
                for elem in row:
                    index_to_pl_name[ind] = elem.strip('"')
                    ind += 1
                continue
            t_uri = row[1].strip('"')
            t_playlist_ids = set()
            for k in range(2, len(row)):
                elem = row[k].strip('"')
                if elem:
                    t_playlist_ids.add(self.playlist_name_to_playlist_id[index_to_pl_name[k]])
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
            try:
                name = self.track_uri_to_track[t_uri][0]
            except KeyError:
                print "track uri {} name not found".format(t_uri) 
                name = "NOT FOUND"

            for pl_id in pl_ids:
                indeces.append(pl_id_to_index[pl_id])

            writestr += u'"{}",'.format(name)
            writestr += u'"{}",'.format(t_uri)

            tot = len(my_playlists)

            while tot > 0:
                write = False
                for k in range(len(indeces)):
                    if indeces[k] == 0:
                        write = True
                    indeces[k] -= 1
                if write:
                    writestr += '"{}",'.format("x")
                else:
                    writestr += '"",'
                tot -= 1

            self.write_line(outfile, writestr)
        
        outfile.close()
        return outfile_name

    def is_old(self, track_uri, track_uri_to_playlist_ids):
        """
        checks if a track uri is an old track.
        """
        old_likes_pl_ids = []
        for name in self.OLD_LIKES_NAMES:
            old_likes_pl_ids.append(self.playlist_name_to_playlist_id[name])

        for old_likes_pl_id in old_likes_pl_ids:
            try:
                if old_likes_pl_id in track_uri_to_playlist_ids[track_uri]:
                    return (True, old_likes_pl_id)
            except KeyError:
                return (False, old_likes_pl_id)

        return (False, "")

    def update_local_data(self, csv_path):
        """
        uses the given csv_path to update the local data sheet.
        Run this after updating the csv to update local data sheet.
        The result of this will be used as a reference to syncing
        spotify playlists.
        """
        track_uri_to_playlist_ids = self.load_csv(csv_path)
        track_uri_to_playlist_ids_local = self.load_csv(self.DATA_FILENAME)
        updated_data = dict()

        for track_uri in (set(track_uri_to_playlist_ids.keys()) | set(track_uri_to_playlist_ids_local.keys())):
            (is_old, old_playlist_id) = self.is_old(track_uri, track_uri_to_playlist_ids)
            (is_old_local, old_playlist_id_local) = self.is_old(track_uri, track_uri_to_playlist_ids_local)
            # merge the playlists and only remove old if remote is not old.
            updated_data[track_uri] = set()
            try:
                # if remote is not old and local is old, then merge and remove local old
                if is_old_local and not is_old:
                    for pl_id in track_uri_to_playlist_ids[track_uri]:
                        updated_data[track_uri].add(pl_id)
                    for pl_id in track_uri_to_playlist_ids_local[track_uri]:
                        updated_data[track_uri].add(pl_id)
                    updated_data[track_uri].remove(old_playlist_id_local)
                # if remote is old, then update with local and add remote old
                elif is_old:
                    for pl_id in track_uri_to_playlist_ids_local[track_uri]:
                        updated_data[track_uri].add(pl_id)
                    updated_data[track_uri].add(old_playlist_id)
                # if remote is not old and local is not old, then update with remote.
                else:
                    for pl_id in track_uri_to_playlist_ids[track_uri]:
                        updated_data[track_uri].add(pl_id)
            # If for some reason you can't find it, then use downloaded data.
            except KeyError:
                try:
                    for pl_id in track_uri_to_playlist_ids[track_uri]:
                        updated_data[track_uri].add(pl_id)
                except KeyError:
                    for pl_id in track_uri_to_playlist_ids_local[track_uri]:
                        updated_data[track_uri].add(pl_id)

        self.make_csv(updated_data, self.DATA_FILENAME)
        self.make_csv(updated_data, csv_path)

    def update_spotify(self, csv_path, really_remove=False):
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

        if os.path.isfile(self.DATA_FILENAME):
            cur_date = datetime.datetime.now()
            date_str = re.sub(r"[ \-\:\.]", "", str(cur_date))[:13]
            cur_spotify_data = self.get_data_from_spotify(update=True)
            self.update_local_data(csv_path)
            data = self.load_csv(self.DATA_FILENAME)
            if not really_remove:
                shutil.copyfile(self.DATA_FILENAME, self.DATA_FILENAME[:-4] + date_str + ".csv")
        else:
            raise ValueError("data sheet file not found. Please pull first.")

        playlist_id_to_tracks_add = dict()
        playlist_id_to_tracks_remove = dict()

        # Sync to spotify.
        for track_uri, playlist_ids in data.iteritems():
            is_old, old_playlist_id = self.is_old(track_uri, data)
            track_id = self.get_id_from_uri(track_uri)

            # If it's in any of old likes, remove it from all spotify playlists that contain it.
            if is_old:
                for playlist_id in playlist_ids:
                    not_in_spotify = False
                    try:
                        not_in_spotify = not (playlist_id in cur_spotify_data[track_uri])
                    except KeyError:
                        not_in_spotify = True
                    if not old_playlist_id == playlist_id and not not_in_spotify:
                        if not playlist_id in playlist_id_to_tracks_remove:
                            playlist_id_to_tracks_remove[playlist_id] = set()
                        playlist_id_to_tracks_remove[playlist_id].add(track_id)
                    # Now add it to old likes
                try:
                    in_spotify = old_playlist_id in cur_spotify_data[track_uri]
                except KeyError:
                    in_spotify = False
                if not in_spotify:
                    if not playlist_id in playlist_id_to_tracks_add:
                        playlist_id_to_tracks_add[old_playlist_id] = set()
                    playlist_id_to_tracks_add[old_playlist_id].add(track_id)
                continue

            # Else if it's in local and not in remote, add
            for playlist_id in playlist_ids:
                if playlist_id not in cur_spotify_data[track_uri]:
                    if not playlist_id in playlist_id_to_tracks_add:
                        playlist_id_to_tracks_add[playlist_id] = set()
                    playlist_id_to_tracks_add[playlist_id].add(track_id)

            # Else if it's in remote and not in local, remove
            for playlist_id in cur_spotify_data[track_uri]:
                if playlist_id not in data[track_uri]:
                    if not playlist_id in playlist_id_to_tracks_remove:
                        playlist_id_to_tracks_remove[playlist_id] = set()
                    playlist_id_to_tracks_remove[playlist_id].add(track_id)

        print "ADD THE FOLLOWING"
        for playlist_id, tracks in playlist_id_to_tracks_add.iteritems():
            if really_remove:
                results = self.spotify.user_playlist_add_tracks(self.USERNAME, playlist_id, list(tracks))
            print self.playlist_id_to_playlist_name[playlist_id]
            for t in tracks:
                try:
                    track_name = self.track_uri_to_track["spotify:track:"+t][0]
                    if not isinstance(track_name, unicode):
                        track_name = unicode(track_name,"utf-8")
                    print u"\t{}".format(track_name)
                except:
                    print u"\tUNICODE ERROR SORRY CANT PRINT NAME or could not find"

        print "REMOVE THE FOLLOWING"
        for playlist_id, tracks in playlist_id_to_tracks_remove.iteritems():
            if really_remove:
                self.spotify.user_playlist_remove_all_occurrences_of_tracks(self.USERNAME, playlist_id, list(tracks))
            print self.playlist_id_to_playlist_name[playlist_id]
            for t in tracks:
                try:
                    track_name = self.track_uri_to_track["spotify:track:"+t][0]
                except KeyError:
                    "spotify track {} not found".format(t)
                try:
                    if not isinstance(track_name, unicode):
                        track_name = unicode(track_name,"utf-8")
                    print u"\t{}".format(track_name)
                except:
                    print u"\tUNICODE ERROR SORRY CANT PRINT NAME"
