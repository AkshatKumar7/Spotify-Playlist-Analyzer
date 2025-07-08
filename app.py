# [1] Importing libraries
import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from collections import Counter, defaultdict
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time
import logging

# [2] Configuration and theming
st.set_page_config(page_title="Spotify Playlist Analyzer", layout="wide")
dark_mode = st.sidebar.toggle("🌙 Dark Mode")  # FIXED UnicodeEncodeError

css_path = "static/css/dark.css" if dark_mode else "static/css/styles.css"
try:
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
except FileNotFoundError:
    st.warning("Custom CSS file not found.")

# [3] Spotify credentials
client_id = st.secrets["SPOTIPY_CLIENT_ID"]
client_secret = st.secrets["SPOTIPY_CLIENT_SECRET"]


auth_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
sp = spotipy.Spotify(auth_manager=auth_manager)

# [4] Sidebar Navigation
st.title("🎵 Spotify Playlist Analyzer")
page = st.sidebar.radio("Navigate", [
    "Home", "Genres", "Top Artists", "Genre Filter", "Release Years", "Compare Playlists"
])

# [5] Playlist input
playlist_link = st.text_input("Paste your Spotify playlist link:")
if playlist_link:
    playlist_URI = playlist_link.split("/")[-1].split("?")[0]

    @st.cache_data(show_spinner=True, ttl=3600)
    def get_all_tracks(_sp, playlist_uri):
        tracks = []
        results = _sp.playlist_tracks(playlist_uri)
        tracks.extend(results["items"])
        while results["next"]:
            try:
                time.sleep(0.2)
                results = _sp.next(results)
                tracks.extend(results["items"])
            except spotipy.exceptions.SpotifyException:
                time.sleep(5)
        return tracks

    try:
        all_tracks = get_all_tracks(sp, playlist_URI)

        genre_list = []
        artist_names = []
        genre_map = {}
        total_duration_ms = 0

        artist_ids = list({
            t["track"]["artists"][0]["id"]
            for t in all_tracks if t.get("track") and t["track"].get("artists")
        })

        artist_cache = {}
        for i in range(0, len(artist_ids), 50):
            batch_ids = artist_ids[i:i + 50]
            try:
                artists = sp.artists(batch_ids)["artists"]
                for artist in artists:
                    artist_cache[artist["id"]] = artist
                time.sleep(0.3)
            except spotipy.exceptions.SpotifyException:
                time.sleep(5)

        artist_track_count = Counter()
        for item in all_tracks:
            track = item.get("track")
            if not track or not track.get("artists"):
                continue

            artist_id = track["artists"][0]["id"]
            artist_name = track["artists"][0]["name"]
            track_name = track["name"]
            preview_url = track.get("preview_url")
            duration = track.get("duration_ms", 0)
            total_duration_ms += duration

            artist_names.append(artist_name)
            artist_track_count[artist_id] += 1

            genres = artist_cache.get(artist_id, {}).get("genres", [])
            genre_list.extend(genres)

            for genre in genres:
                genre_map.setdefault(genre, []).append({
                    "track_name": track_name,
                    "artist_name": artist_name,
                    "preview_url": preview_url,
                    "image_url": track["album"]["images"][0]["url"]
                    if track.get("album") and track["album"].get("images") else "",
                    "spotify_url": track["external_urls"]["spotify"]
                    if track.get("external_urls") else ""
                })

        def format_duration(ms):
            seconds = ms // 1000
            h = seconds // 3600
            m = (seconds % 3600) // 60
            s = seconds % 60
            return f"{h}h {m}m {s}s"

        genre_df = pd.DataFrame(Counter(genre_list).items(), columns=["Genre", "Count"]).sort_values("Count", ascending=False)

        top_artists_data = []
        for artist_id, count in artist_track_count.items():
            artist = artist_cache.get(artist_id)
            if artist:
                top_artists_data.append({
                    "Name": artist["name"],
                    "Tracks in Playlist": count,
                    "Spotify URL": artist["external_urls"]["spotify"],
                    "Image": artist["images"][0]["url"] if artist["images"] else None
                })

        top_artists_df = pd.DataFrame(top_artists_data).sort_values("Tracks in Playlist", ascending=False).head(20)

        st.success(f"✅ Total Songs: **{len(all_tracks)}**")
        st.success(f"⏲️ Total Playlist Duration: **{format_duration(total_duration_ms)}**")
        
        artist_map = defaultdict(list)

        if page == "Genres":
            st.header("📊 Top Genres")
            fig = px.bar(genre_df.head(10), x='Genre', y='Count', color='Genre',
                         color_discrete_sequence=px.colors.qualitative.Safe)
            st.plotly_chart(fig, use_container_width=True)
            csv = genre_df.to_csv(index=False).encode()
            st.download_button("⬇️ Download Genre CSV", csv, "genres.csv", "text/csv")

            # Genre Clustering (Feature #9)
            genre_clusters = defaultdict(int)
            for genre in genre_list:
                g = genre.lower()
                if "indie" in g:
                    genre_clusters["Indie"] += 1
                elif "pop" in g:
                    genre_clusters["Pop"] += 1
                elif "rock" in g:
                    genre_clusters["Rock"] += 1
                elif "hip hop" in g or "rap" in g:
                    genre_clusters["Hip-Hop / Rap"] += 1
                elif "electronic" in g or "edm" in g or "house" in g or "techno" in g:
                    genre_clusters["Electronic"] += 1
                elif "metal" in g:
                    genre_clusters["Metal"] += 1
                elif "jazz" in g:
                    genre_clusters["Jazz"] += 1
                elif "r&b" in g or "soul" in g:
                    genre_clusters["R&B / Soul"] += 1
                elif "country" in g:
                    genre_clusters["Country"] += 1
                elif "funk" in g or "disco" in g:
                    genre_clusters["Funk / Disco"] += 1
                else:
                    genre_clusters["Other"] += 1

            df_genre_clusters = pd.DataFrame(
                sorted(genre_clusters.items(), key=lambda x: x[1], reverse=True),
                columns=["Genre Family", "Count"]
            )

            st.subheader("🧬 Genre Families (Clustered by Keyword)")
            fig_cluster = px.bar(df_genre_clusters, x="Genre Family", y="Count", color="Genre Family",
                                 title="🎚️ Genre Family Breakdown", text="Count")
            st.plotly_chart(fig_cluster, use_container_width=True)

            st.subheader("🥧 Genre Family Pie Chart")
            pie_chart = px.pie(df_genre_clusters, values="Count", names="Genre Family",
                               title="🔸 Genre Family Distribution", hole=0.4)
            st.plotly_chart(pie_chart, use_container_width=True)

            if st.toggle("🌳 Show Genre Family Treemap"):
                st.subheader("🌳 Genre Family Treemap")
                treemap = px.treemap(df_genre_clusters, path=["Genre Family"], values="Count",
                                     color="Genre Family", title="🧱 Genre Family Tree Map")
                st.plotly_chart(treemap, use_container_width=True)

        
        elif page == "Genre Filter":
            st.header("🎯 Filter by Genre")
            all_genres = sorted(list(genre_map.keys()))
            selected_genre = st.selectbox("Select a genre", all_genres)

            if selected_genre in genre_map:
                st.subheader(f"Tracks in Genre: **{selected_genre}**")
                for track in genre_map[selected_genre]:
                    st.markdown(f"""
                    <div style='display: flex; align-items: center; gap: 10px; margin-bottom: 1rem;'>
                        <img src="{track['image_url']}" width="64" height="64" style="border-radius: 8px;" />
                        <div>
                            <strong>{track['track_name']}</strong><br>
                            <em>{track['artist_name']}</em><br>
                            <a href="{track['spotify_url']}" target="_blank">Open in Spotify</a>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)


        elif page == "Top Artists":
            st.header("🎼 Top 20 Artists in Playlist")
            st.markdown("These are the most featured artists in your playlist. Click their names to open them in Spotify.")

            for index, row in top_artists_df.iterrows():
                artist_name = row["Name"]
                track_count = row["Tracks in Playlist"]
                spotify_url = row["Spotify URL"]
                image_url = row["Image"] or "https://via.placeholder.com/100?text=No+Image"

                col1, col2 = st.columns([1, 4])

                with col1:
                    st.image(image_url, width=80)

                with col2:
                    st.markdown(f"""
                        <div style="padding: 0.3rem 0.5rem; border-left: 3px solid #1DB954;">
                            <h4 style="margin: 0; padding: 0;">
                                <a href="{spotify_url}" target="_blank" style="text-decoration: none; color: #1DB954;">
                                    {artist_name}
                                </a>
                            </h4>
                            <p style="margin: 0.2rem 0; color: #555;">
                                🎵 <strong>{track_count}</strong> track(s) in your playlist
                            </p>
                        </div>
                    """, unsafe_allow_html=True)

                st.markdown("<hr style='margin-top: 1rem; margin-bottom: 1rem;'>", unsafe_allow_html=True)


        elif page == "Artist Filter":
            st.header("🎤 Filter by Artist")
            all_artists = sorted(list(artist_map.keys()))
            selected_artist = st.selectbox("Select an artist", all_artists)

            if selected_artist in artist_map:
                st.subheader(f"🎵 Tracks by {selected_artist}")
                for track in artist_map[selected_artist]:
                    st.markdown(f"""
                    <div style='display: flex; align-items: center; gap: 15px; margin-bottom: 1rem; background-color: #f9f9f9; padding: 10px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);'>
                        <img src="{track['image_url']}" width="70" height="70" style="border-radius: 10px;" />
                        <div>
                            <div style='font-size: 18px; font-weight: 600;'>{track['track_name']}</div>
                            <a href="{track['spotify_url']}" target="_blank" style='color: #1DB954;'>🎧 Open in Spotify</a>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

        elif page == "Release Years":
            st.header("📅 Release Year Analysis")
            release_years = []
            for item in all_tracks:
                track = item.get("track")
                if not track:
                    continue
                album = track.get("album", {})
                release_date = album.get("release_date")
                if release_date:
                    year = release_date[:4]
                    if year.isdigit():
                        release_years.append(int(year))

            if release_years:
                year_counts = Counter(release_years)
                year_df = pd.DataFrame(sorted(year_counts.items()), columns=["Year", "Track Count"])

                # Histogram
                st.subheader("📊 Histogram of Release Years")
                fig_hist = px.histogram(year_df, x="Year", y="Track Count",
                                        nbins=len(year_df),
                                        title="Tracks by Release Year",
                                        labels={"Track Count": "Tracks"},
                                        color_discrete_sequence=["#1DB954"])
                st.plotly_chart(fig_hist, use_container_width=True)

                # Decade View
                st.subheader("🧮 Tracks by Decade Range")
                def get_decade_label(year):
                    start = (year // 10) * 10
                    return f"{start}s ({start}-{start + 9})"

                year_df["Decade Range"] = year_df["Year"].apply(get_decade_label)
                decade_range_df = year_df.groupby("Decade Range")["Track Count"].sum().reset_index()

                fig_decade = px.bar(decade_range_df, x="Decade Range", y="Track Count",
                                    title="Tracks by Decade Range",
                                    labels={"Track Count": "Tracks"},
                                    color="Track Count", color_continuous_scale="blues")
                st.plotly_chart(fig_decade, use_container_width=True)

                # Data Table
                st.subheader("📋 Yearly Breakdown")
                st.dataframe(year_df, use_container_width=True)

                csv = year_df.to_csv(index=False).encode()
                st.download_button("⬇️ Download Year Data CSV", csv, "release_years.csv", "text/csv")
            else:
                st.warning("Could not extract release years from the tracks.")

        elif page == "Compare Playlists":
            st.header("🔍 Compare Two Playlists")
            pl1 = st.text_input("Enter the first playlist link:")
            pl2 = st.text_input("Enter the second playlist link:")

            def extract_uri(link):
                return link.split("/")[-1].split("?")[0]

            def get_summary(uri):
                tracks = get_all_tracks(sp, uri)
                artists = [
                    t["track"]["artists"][0]["name"]
                    for t in tracks if t.get("track") and t["track"].get("artists")
                ]
                genres = []
                ids = list({t["track"]["artists"][0]["id"]
                            for t in tracks if t.get("track") and t["track"].get("artists")})
                for i in range(0, len(ids), 50):
                    batch = sp.artists(ids[i:i + 50])["artists"]
                    for a in batch:
                        genres.extend(a.get("genres", []))
                return Counter(artists), Counter(genres), len(tracks)

            if pl1 and pl2:
                try:
                    uri1, uri2 = extract_uri(pl1), extract_uri(pl2)
                    name1 = sp.playlist(uri1)['name']
                    name2 = sp.playlist(uri2)['name']
                    a1, g1, t1 = get_summary(uri1)
                    a2, g2, t2 = get_summary(uri2)

                    st.subheader("🎶 Total Tracks")
                    col1, col2 = st.columns(2)
                    col1.metric(name1, t1)
                    col2.metric(name2, t2)

                    common_artists = set(a1.keys()) & set(a2.keys())
                    total_unique_artists = set(a1.keys()) | set(a2.keys())
                    artist_overlap_pct = len(common_artists) / len(total_unique_artists) * 100 if total_unique_artists else 0

                    common_genres = set(g1.keys()) & set(g2.keys())
                    all_genres = set(g1.keys()) | set(g2.keys())
                    genre_overlap_pct = len(common_genres) / len(all_genres) * 100 if all_genres else 0

                    overall_similarity = (artist_overlap_pct + genre_overlap_pct) / 2

                    st.subheader("🔗 Overall Playlist Similarity")
                    st.metric(label="Similarity Score", value=f"{overall_similarity:.2f}%")

                    st.subheader(f"🎼 Similar Artists ({artist_overlap_pct:.2f}% Overlap)")
                    df_similar_artists = pd.DataFrame([
                        {"Artist": artist, name1: a1.get(artist, 0), name2: a2.get(artist, 0)}
                        for artist in sorted(common_artists, key=lambda a: a1.get(a, 0) + a2.get(a, 0), reverse=True)
                    ])
                    if not df_similar_artists.empty:
                        fig = go.Figure()
                        fig.add_trace(go.Bar(x=df_similar_artists["Artist"], y=df_similar_artists[name1], name=name1))
                        fig.add_trace(go.Bar(x=df_similar_artists["Artist"], y=df_similar_artists[name2], name=name2))
                        fig.update_layout(barmode='group', title="🎼 Common Artists", xaxis_tickangle=-45)
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("No common artists found.")

                    st.subheader(f"🎧 Similar Genres ({genre_overlap_pct:.2f}% Overlap)")
                    df_similar_genres = pd.DataFrame([
                        {"Genre": genre, name1: g1.get(genre, 0), name2: g2.get(genre, 0)}
                        for genre in sorted(common_genres, key=lambda g: g1.get(g, 0) + g2.get(g, 0), reverse=True)
                    ])
                    if not df_similar_genres.empty:
                        fig_genre = go.Figure()
                        fig_genre.add_trace(go.Bar(x=df_similar_genres["Genre"], y=df_similar_genres[name1], name=name1))
                        fig_genre.add_trace(go.Bar(x=df_similar_genres["Genre"], y=df_similar_genres[name2], name=name2))
                        fig_genre.update_layout(barmode='group', title="🎧 Common Genres", xaxis_tickangle=-45)
                        st.plotly_chart(fig_genre, use_container_width=True)
                    else:
                        st.info("No common genres found.")
                except Exception as e:
                    st.error(f"Error comparing playlists: {e}")

    except Exception as e:
        st.error(f"⚠️ Error loading playlist: {e}")
