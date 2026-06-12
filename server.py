import socket
import threading
import os
import bcrypt
import sqlite3
import uuid
from datetime import datetime , timedelta
import time
import shutil
import traceback
import subprocess



def create_db():
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        #creating database for username and passwords
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users(
                   user_id INTEGER PRIMARY KEY,
                   user_name TEXT NOT NULL UNIQUE,
                hashed_passwd TEXT NOT NULL

                    )
            """)

        #creating databse for playlists and holding user
        cursor.execute("""
                CREATE TABLE IF NOT EXISTS playlists(
                    playlist_id INTEGER PRIMARY KEY,
                    playlist_name TEXT NOT NULL,
                    user_id INTEGER NOT NULL

                    )
            """)

        #creating database for songs
        cursor.execute("""
                CREATE TABLE IF NOT EXISTS songs(
                        song_id INTEGER PRIMARY KEY,
                        song_name TEXT NOT NULL,
                        artist_id INTEGER NOT NULL,
                        genre_id INTEGER NOT NULL,
                        album_id INTEGER NOT NULL             
                        )
                """)


        #creating database for assinging songs to playlits
        cursor.execute("""
                CREATE TABLE IF NOT EXISTS playlist_songs(
                        playlist_id INTEGER NOT NULL,
                        song_id INTEGER NOT NULL,
                       PRIMARY KEY (playlist_id, song_id)
                        )
                """)


        #creating database for artists
        cursor.execute("""
                CREATE TABLE IF NOT EXISTS artists(
                        artist_id INTEGER PRIMARY KEY,
                        artist_name TEXT NOT NULL
               
                       )
                """)


        #creating databse for albums
        cursor.execute("""
                CREATE TABLE IF NOT EXISTS albums(
                        album_id INTEGER PRIMARY KEY,
                        album_name TEXT NOT NULL,
                        artist_id INTEGER NOT NULL 
                        )
                """)

        #creating database for genres
        cursor.execute("""
                CREATE TABLE IF NOT EXISTS genres(
                        genre_id INTEGER PRIMARY KEY,
                        genre_name TEXT NOT NULL

                        )        
                """) 

        #creating databse for song history
        cursor.execute("""
                CREATE TABLE IF NOT EXISTS history(
                        history_id INTEGER PRIMARY KEY,
                        song_id INTEGER,
                        song_name TEXT NOT NULL,
                        user_id INTEGER NOT NULL,
                        played_time TEXT NOT NULL
                       )
             """)

        #creating active bans databse table
        cursor.execute("""
                CREATE TABLE IF NOT EXISTS active_bans(
                       ban_id INTEGER PRIMARY KEY,
                       ip_address TEXT NOT NULL,
                       banned_at TEXT NOT NULL,
                       expires_at TEXT NOT NULL
                       )
        """)

        conn.commit()
        conn.close()


        print("database created sucessfully!")
        

os.makedirs("backups", exist_ok = True) 
os.makedirs("cache", exist_ok = True)

def heartbeat_monitoring(active_users):

    while True:
    
        for user in active_users.values():

            with user.lock:

                time_elapsed = time.time() - user.last_heartbeat

                if time_elapsed > 30 and user.connected:
                    print(f"{user.sessionId} disconnected")
                
                
                    try:
                        if user.client_socket:
                            user.client_socket.close()
                            user.connected = False

                    except:
                        pass
        time.sleep(5)


def backup():

    while True:
        time_stamp = datetime.now().strftime( " %d-%m-%Y_%H-%M-%S " )

        backup_file = os.path.join(
            "backups",
            f"backup_{time_stamp}.db"
        )

        shutil.copy(
            "users.db",
            backup_file
        )

        time.sleep(300)

backup_thread = threading.Thread(
    target = backup,
    daemon=True
)


backup_thread.start()
#loading songs into the database
def load_songs():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    songs = os.listdir("songs")
    print(songs)
    for song in songs:
        cursor.execute("""
                SELECT song_id
                FROM songs
                WHERE song_name = ?
            """,(song,))
        result2 = cursor.fetchone()
        if result2 is None:
            cursor.execute("""
                    INSERT INTO songs(song_name, artist_id, genre_id, album_id)
                    VALUES(?,?,?,?)                    
                """,(song,0,0,0,))
            print("Song inserted successfullt!")
        else:
            song_id = result2[0]
            print("song already exist with song Id:" + str(song_id))
    conn.commit()
    conn.close()


#creating userstate
class userState:
    def __init__(self,session_id,user_id):
        self.sessionId = session_id
        self.user_id = user_id
        self.current_song = None
        self.position = 0
        self.queue = []
        self.buffer_health = 100
        self.client_socket = None
        self.stop_stream = False
        self.stream_thread = False
        self.lock = threading.Lock()
        self.socket_version = 0
        self.last_heartbeat = time.time()
        self.connected = True


#creating a socket server
server = socket.socket()
server.bind(("127.0.0.1", 8888))
server.listen(5)

create_db()
load_songs()

# Function to handle user signup
def signup(username, password):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
    SELECT user_name FROM users
    WHERE user_name = ?

        """,(username,))
    result = cursor.fetchone()
    if result is None:
        hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
        cursor.execute("""
        INSERT INTO users(user_name, hashed_passwd)
        VALUES(?,?)

        """,(username, hashed_password,))
        conn.commit()
        cursor.execute("""
                SELECT user_id FROM users
                WHERE user_name = ?
                """,(username,))
        result1 = cursor.fetchone()
        user_id = result1[0]
        conn.commit()
        conn.close() 
        return user_id      
    else:
        conn.close()
        print("User already exist! Try login")
        return False



def login(username, password):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT hashed_passwd, user_id FROM users
        WHERE user_name = ?
        """,(username,))
    result = cursor.fetchone()
    conn.close() 
    if result is None:
        print("user doesn't exist!")
        return False
    else:
        stored_hash = result[0]
        user_id = result[1]
        checking = bcrypt.checkpw(
            password.encode(),
            stored_hash
            )
        if checking:
            print("SUCCESS")
            return user_id
        else:
            print("Wrong user credintals! Try again later")
            return False       


def stream_song(user):
    
    path = os.path.join("songs", user.current_song)
    print("Current Song:", user.current_song)
    print("SIZE:", os.path.getsize(path))  

    if os.path.exists(path):

        print(f"Sending {user.current_song} chunk from:", user.position)
        with open(path, "rb") as file:
            with user.lock:
                offset = 4096*user.position
            file.seek(offset)
            data = file.read(4096)

            curr_version = user.socket_version 



            while data:
                while True:
                    with user.lock:
                        if not user.stop_stream:
                            break

                    time.sleep(0.1)
                
                try:
                    with user.lock:
                        if user.socket_version != curr_version:
                            return
                    
                    user.client_socket.sendall(data)
                    time.sleep(0.1)

                except OSError:
                    print(f"Client disconnected while streaming {user.current_song}.mp3 at chunk:", user.position)
                    return
                        
                data = file.read(4096)
                with user.lock:
                    user.position += 1

                        
            try:
                user.client_socket.sendall(b"EOF")
                return
            except:
                pass



        with user.lock:
            user.socket_version += 1

            if len(user.queue) > 0:
                next_song = user.queue.pop(0)
                user.current_song = next_song
                user.position = 0
                start_next = True

            else:
                user.current_song = None
                user.position = 0
                return
         
        if start_next:
            threading.Thread(
                target = stream_song,
                args = (user,)
            ).start()

    else:
        user.client_socket.send("Song not found".encode())


def talk_to_client(server_client, address, user):
    if user is None:
        server_client.close()
        return
    
    
    print("ENTERED THREAD")
    print("SESSION ID:" + str(user.sessionId))
    print("USER ID:" + str(user.user_id))

    
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    print("connected to:", address)
    while True:
        try:
            message = server_client.recv(1024).decode()
            if not message:
                print("client disconnected")
                break

            if message != "HEARTBEAT":
                print("client says:", message)
            
            # Handle client messages and commands here
            if message == "LIST":
                    cursor.execute("""
                                SELECT song_name FROM songs
                                
                """)
                    songs = cursor.fetchall()
                    if songs:
                        song_list = "\n".join(song[0] for song in songs )
                    else:
                        song_list = "songs not found"
                    server_client.send(song_list.encode())
            

            elif message == "HEARTBEAT":

                with user.lock:
                    user.last_heartbeat = time.time()
                    continue


            elif message.startswith("PLAY|"):
            
                song_name = message.split("|", 1)[1]
                
                #check if the song exists
                cursor.execute("""
                        SELECT song_id FROM songs
                        WHERE song_name = ?
                """,(song_name,))

                result = cursor.fetchone()

                if result is None:
                    server_client.send("Song Not found".encode())

                else:
                    song_id = result[0]

                    with user.lock:
                        user.socket_version += 1
                        user.current_song = song_name
                        user.position = 0
                        user.stop_stream = False

                    thread_play = threading.Thread(
                        target = stream_song,
                        args = (user,)
                    )


                    played_time = datetime.now().strftime( "%d/%m/%Y, %H:%M:%S")
                    #adding that song into the history
                    cursor.execute("""
                            INSERT INTO history(song_id, user_id, song_name,played_time)
                            VALUES(?,?,?,?)
                    """,(song_id, user.user_id, song_name, played_time))
                    conn.commit()

                    user.stop_stream = False
                    with user.lock:
                        user.current_song = song_name
                    

                    user.thread_stream = thread_play
                    thread_play.start()



            elif message == "PAUSE":
                print("Pause Recieved")
                with user.lock:
                    user.stop_stream = True
                    user.buffer_health = max(0, user.buffer_health - 10) 
                
                

            elif message == "RESUME":
                with user.lock:
                    user.stop_stream = False
            

            elif message.startswith("CREATE_PLAYLIST"):

                try:



                    #creating the playlist and adding songs
                    playlist = message.split(" ",1)[1]

                    conn.execute("BEGIN")

                    cursor.execute("""
                            INSERT INTO playlists(playlist_name, user_id)
                            VALUES(?,?)
                            """,(playlist, user.user_id,))

                    #taking playlist id
                    playlist_id = cursor.lastrowid 

                    while True:

                        server_client.send("Add add into the playlist or type 'DONE' to save the final playlist".encode())
                        #getting the song name 
                        data = server_client.recv(1024)
                        if not data:
                            print("No song name!")
                        
                        song_name = data.decode()
                        if song_name == "DONE":
                            break
                        #getting song id
                        cursor.execute("""
                                SELECT song_id FROM songs
                                WHERE song_name = ?
                            """,(song_name,))
                        result_song_id = cursor.fetchone()


                        if result_song_id is None:
                            raise Exception("Opps Could not find song!")
                        else:
                            song_id = result_song_id[0]


                            #adding songs to the playlist
                            cursor.execute("""
                                    INSERT INTO playlist_songs(playlist_id, song_id)
                                    VALUES(?,?)
                            """,(playlist_id, song_id,))


                    conn.commit()

                    #reassuring the client
                    server_client.send("\nPlaylist created and songs song added successflly:)".encode())

                except Exception as e:
                    conn.rollback()
                    print("Error:", e)
                    server_client.send("Failed to create the playlist! Try again".encode())

            elif message == "NEXT":
                with user.lock:
                    user.socket_version += 1

                    if len(user.queue) > 0:
                        user.position = 0
                        next_song = user.queue.pop(0)
                        user.current_song = next_song
                        user.stop_stream = False

                        threading.Thread(
                            target = stream_song,
                            args = (user,)
                        ).start()
                    else:
                        user.current_song = None
                        user.position = 0


            elif message == "ADD SONGS":
                playlist_name = server_client.recv(1024).decode()
                print(playlist_name)
                #getting playlist Id
                cursor.execute("""
                        SELECT playlist_id FROM playlists
                        WHERE playlist_name = ? and user_id = ?
                """,(playlist_name, user.user_id,))
                result = cursor.fetchone()
                if result is None:
                    print("NO playlist found!")
                    continue
                else:
                    playlist_id = result[0]
                    print(playlist_id)
                while True:
                    song_name = server_client.recv(1024).decode()
                    print(song_name)
                    if song_name == "DONE":
                        break
                    #getting song id
                    cursor.execute("""
                            SELECT song_id FROM songs
                            WHERE song_name = ?
                    """,(song_name,))
                    result = cursor.fetchone()
                    if result is None:
                        print("\nNo song Id sound")
                        return
                    else:
                        song_id = result[0]
                        print(song_id)

                        #checking if song already exist in the playlist
                        cursor.execute("""
                                SELECT playlist_id, song_id FROM playlist_songs
                                WHERE playlist_id = ? AND song_id = ?
                        """,(playlist_id, song_id,))
                        result = cursor.fetchone()
                        if result is None:
                            #inserting song into the playlist
                            cursor.execute("""
                                    INSERT INTO playlist_songs(playlist_id, song_id)
                                    VALUES(?, ?)
                            """,(playlist_id, song_id,))
                            conn.commit()
                            #talking to client
                            server_client.send("Song added successfully".encode())
                        else:
                            server_client.send("Song already exist in the playlist".encode())

                        

                    
                server_client.send("Songs added successfully!.".encode())

            elif message.startswith("QUEUE"):
                song_name = message.split("|", 1)[1]

                cursor.execute("""
                        SELECT song_id FROM songs
                        WHERE song_name = ?
                """,(song_name,))
                result = cursor.fetchone()

                print("Current Song:", user.current_song)

                if result is None:
                    server_client.send("Song not found".encode())
                

                
                elif user.current_song is None:
                    with user.lock:
                        user.current_song = song_name
                        user.position = 0
                        user.stop_stream = False

                    threading.Thread(
                        target = stream_song,
                        args = (user,)
                    ).start()
                    
                else:
                    with user.lock:
                        user.queue.append(song_name)
                    




            elif message == "MY PLAYLISTS":
                cursor.execute("""
                        SELECT playlist_name
                        FROM playlists
                        WHERE user_id = ?
            """,(user.user_id,))
                result = cursor.fetchall()
                if not result:
                    server_client.send("NO playlist created".encode())
                else:
                    playlists = "\n".join(playlist[0] for playlist in result)
                    server_client.send(playlists.encode())

            elif message == "PLAYED HISTORY":
                cursor.execute("""
                        SELECT song_name, played_time
                        FROM history
                        WHERE user_id = ?
                """,(user.user_id,))
                result = cursor.fetchall()
                if not result:
                    conn.commit()
                    server_client.send("No History Found".encode())
                else:
                    history = "\n".join(f"{song[0]},{song[1]}" for song in result)
                    server_client.send(history.encode())

            else:
                server_client.send("Song not found".encode())  
              
        except Exception as e:
            print("Error",e)  
            traceback.print_exc()
            break
    conn.close()
    server_client.close()

failed_logins = {}
active_users = {}
connection_attempts = {}

while True:
    access = False
    auth = False
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    server_client, address = server.accept()
    choice = server_client.recv(1024).decode()
    ip = address[0]

    if ip not in connection_attempts:
        connection_attempts[ip] = []


    curr_time = time.time()
    connection_attempts[ip].append(curr_time)

    connection_attempts[ip] = [
        t for t in connection_attempts[ip]
        if curr_time - t < 60
    ]


    if len(connection_attempts[ip]) > 3:
        print("Rate limit exeeded")
        server_client.close()
        continue
    
    #checking if the user is in active bans
    cursor.execute("""
            SELECT expires_at FROM active_bans
            where ip_address = ?
    """,(ip,))
    result = cursor.fetchone()
    if result is None:
        access = True
    else:
        expires_at = datetime.fromisoformat(result[0])
        
        if expires_at > datetime.now():
            print("This ip address is banned currently for some time")
            server_client.close()
            continue
        else:
            cursor.execute("""
                    DELETE FROM active_bans
                    WHERE ip_address = ?
        """,(ip,))
            conn.commit()
            failed_logins.pop(ip, None)
            access = True


    if access:
        reconnected = False
        if choice == "1": 
            username = server_client.recv(1024).decode()
            password = server_client.recv(1024).decode()
            auth = login(username, password)
        elif choice == "2":
            username = server_client.recv(1024).decode()
            password = server_client.recv(1024).decode()
            auth = signup(username, password)
        elif choice == "3":
            message = server_client.recv(1024).decode()
            if message.startswith("RECONNECT"):
                session_id = message.split(" ",1)[1]

                print("Session id:", session_id)
                print("Active users:",active_users.keys())


                if session_id in active_users:
                
                    user = active_users[session_id]


                    with user.lock:
                        old_socket = user.client_socket
                        user.client_socket = server_client
                    try:
                        if old_socket:
                            old_socket.close()
                    except:
                        pass
                    
                    auth = user.user_id
                    reconnected = True

                    with user.lock:
                        user.buffer_health = max(0, user.buffer_health - 20)

                    threading.Thread(
                        target = stream_song,
                        args = (user,),
                        daemon=True
                    ).start()

                else:
                    auth = False
                    server_client.send("INVALID SESSION".encode())
                    reconnected = False
        else:
            auth = False
            server_client.send("Invalid choice!".encode())
            conn.commit()
            



    if auth:
        
        if ip in failed_logins:
            del failed_logins[ip]
        server_client.send("SUCCESS".encode())
        if not reconnected:
            sessionId = str(uuid.uuid4())

            user = userState(sessionId, auth)
            user.client_socket = server_client
            active_users[sessionId]=user
            print("Added session:", sessionId)
            print("Active users:", active_users.keys())


            thread = threading.Thread(
                target = talk_to_client,
                args = (server_client, address, user)
            )
    
            thread.start()

            
            threading.Thread(
                target = heartbeat_monitoring,
                args = (active_users,),
                daemon = True
            ).start()
        else:

            thread = threading.Thread(
                target = talk_to_client,
                args = (server_client, address, user)
            )
    
            thread.start()

    else:
        if ip in failed_logins:
            failed_logins[ip] += 1
        else:
            failed_logins[ip] = 1

        if failed_logins[ip] >= 5:
            banned_at = datetime.now()
            expires_at = banned_at + timedelta(minutes = 30)
            cursor.execute("""
                    SELECT ban_id FROM active_bans
                    WHERE ip_address = ?
            """,(ip,))
            result = cursor.fetchone()
            if result is None:
                cursor.execute("""
                    INSERT INTO active_bans(ip_address, banned_at, expires_at)
                    VALUES(?,?,?)
            """,(ip, banned_at.isoformat(), expires_at.isoformat(),))
                conn.commit()
        server_client.send("Authentication failed. Please try again.".encode())
    conn.close()
