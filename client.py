import socket
import threading
from pydub import AudioSegment
from pydub.playback import play
import time
import queue
import pyaudio

client = socket.socket()
client.connect(("127.0.0.1", 8888))

#login or signup for users
choice = input("1. login ( if you have an account)\n" + "2. signup (if you  are new user)\n" + "3. Already a user, wants to reconnect\n")
client.send(choice.encode())


if choice == "3":
    session_id = input("Enter your old session Id:")
    message = "RECONNECT " + session_id
    client.send(message.encode())
else:
    #asking user for username and password
    username = input("Choose a username: ")
    client.send(username.encode())
    password = input("Choose a password: ")
    client.send(password.encode())

auth = client.recv(1024).decode()
print("SERVER SENT:", auth)

def heartbeat_sender(client_socket):

    while True:
        try:
                client_socket.send("HEARTBEAT".encode())
                time.sleep(5)
        except:
                break
        
audio_queue = queue.Queue(maxsize=100)

def player():
    chunk  = audio_queue.get()
    play(chunk)

if auth == "SUCCESS":
    print("Authentication successful. You can access the music library.")

    threading.Thread(
        target = heartbeat_sender,
        args = (client,),
        daemon = True
    ).start()

    def recv_song(file_name):
        while True:
             
            data = client.recv(4096)
            
            if not data:
                break

            if b'EOF' in data:
                data = data.replace(b"EOF", b"")
                if data:
                    audio_queue.put(data)
                break

            audio_queue.put(data)

            print("Audio buffer queuesize:" , audio_queue.qsize())



    


    while True:
        #asking user for choice
        print("1. PLAY\n" + "2. EXIT\n" + "3. PAUSE\n" + "4. CREATE PLAYLIST\n" + "5. ADD SONGS\n" + "6. MY PLAYLISTS\n" + "7. PLAYED HISTORY\n" + "8. RESUME\n" + "9. ADD QUEUE\n" + "10. NEXT\n" + "11. LIST\n")
        choice = input("Enter your choice:")

        if choice == "11":
            #requesting music list from server  
            client.send("LIST".encode())
            Music_list = client.recv(2048).decode()
            print("Music list:")
            print(Music_list)
        
        
        elif choice == "1":
            message = input("Send song name to server:")
            command = "PLAY|" + message
            file_name = message
            client.send(command.encode())

            recv_thread = threading.Thread(
                target = recv_song,
                args = (file_name,)
            )

            recv_thread.start()


        elif choice == "2":
            print("Exiting...")
            exit()

        elif choice == "3":
            client.send("PAUSE".encode())


        elif choice == "4":
            message = input("Enter the playlist name you want to create:")
            client.send("CREATE_PLAYLIST ".encode() + message.encode())
           
        
            while True:
                responce = client.recv(1024).decode()
                print(responce)
                message = input("\nType Song or DONE:\n")
                client.send(message.encode())
                if message == "DONE":
                    break
            
            responce = client.recv(1024).decode()
            print(responce)


        elif choice == "5":
            client.send("ADD SONGS".encode())
            message = input("Enter playlist name:\n")
            client.send(message.encode())

            while True:

                message = input("\nType song name or DONE:\n")
                client.send(message.encode())
                responce = client.recv(1024).decode()
                print(responce)
                if message == "DONE":
                    break
                
            responce = client.recv(1024).decode()
            print(responce)


        elif choice == "6":
            client.send("MY PLAYLISTS".encode())
            responce = client.recv(2048).decode()
            print(responce)

        elif choice == "7":
            client.send("PLAYED HISTORY".encode())
            responce = client.recv(2048).decode()
            print(responce)

        elif choice == "8":
            client.send("RESUME".encode())

        elif choice == "9":
            message = input("Enter the song you want to add to queue:\n")
            client.send("QUEUE|".encode() + message.encode())
            
        
        elif choice == "10":
            client.send("NEXT".encode())
        
        else:
            print("Invalid choice. Please try again.")

else:
    print("Authentication failed. Please try again.")
client.close()
