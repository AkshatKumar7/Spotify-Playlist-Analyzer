import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from collections import Counter
import matplotlib.pyplot as plt

# ✅ Spotify credentials (remove any spaces!)
client_id = '8d3f75c1531345ce8ce8e16a6cd328b2'
client_secret = 'fedfd53703d54e71bd23ad1ab3e7ed81'

auth_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
sp = spotipy.Spotify(auth_manager=auth_manager)

# ✅ Playlist link
playlist_link = "https://open.spotify.com/playlist/4RhSMoOejI5QLsbSGf9VMy?si=36fcf2f174364ac2"
playlist_URI = playlist_link.split("/")[-1].split("?")[0]

# ✅ Function to get ALL tracks (handles pagination)
def get_all_tracks(sp, playlist_URI):
    tracks = []
    results = sp.playlist_tracks(playlist_URI)
    tracks.extend(results['items'])

    while results['next']:
        results = sp.next(results)
        tracks.extend(results['items'])

    return tracks

# ✅ Get all tracks from the playlist
all_tracks = get_all_tracks(sp, playlist_URI)

# ✅ Extract genres
genre_list = []

for item in all_tracks:
    try:
        artist_id = item['track']['artists'][0]['id']
        artist = sp.artist(artist_id)
        genres = artist.get('genres', [])
        genre_list.extend(genres)
    except Exception as e:
        print("Skipping a track due to error:", e)
        continue

# ✅ Count and display genre distribution
genre_count = Counter(genre_list)

print("\n🎵 Genre Breakdown:")
for genre, count in genre_count.most_common():
    print(f"{genre}: {count}")

# ✅ Plot the top 10 genres
if genre_count:
    labels, values = zip(*genre_count.most_common(10))

    plt.figure(figsize=(10, 6))
    plt.bar(labels, values, color='skyblue')
    plt.xticks(rotation=45)
    plt.title("Top Genres in Playlist")
    plt.tight_layout()
    plt.show()
else:
    print("No genre data found.")
