import spotipy
import sys
import secrets
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
			except NameError:
				playlists = self.spotify.user_playlists(self.USERNAME)
				update = True

		if update:
			for pl in playlists["items"]:
				if pl["owner"]["id"] == self.USERNAME:
					output.append(pl)
			self.playlists = output

		return output

	def make_csv(self):
		"""
		generates a local csv with my spotify playlists.
		"""
		my_playlists = self.get_my_playlists()
		for pl in my_playlists:
			pl_uri = pl["uri"]
			pl_name = pl["name"]
			uri_elems = pl_uri.split(":")
			pl_id = uri_elems[-1]
			tracks = self.spotify.user_playlist_tracks(self.USERNAME, playlist_id=pl_id)



	def update_spotify(self):
		"""
		Updates spotify playlists from local csv.
		"""