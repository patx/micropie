import socketio
import eventlet
from MicroPie import Server

sio = socketio.Server(cors_allowed_origins="*")
app = Server()
active_users = set()

class MyApp(Server):
    def index(self):
        return self.render_template('index.html')

    def submit(self, username, action):
        if username:
            active_users.add(username)
            if action == 'Start Streaming':
                return self.redirect(f'/stream/{username}')
            elif action == 'Watch Stream':
                return self.redirect(f'/watch/{username}')
        return self.redirect('/')

    def stream(self, username):
        if username not in active_users:
            return self.redirect('/')
        return self.render_template('stream.html', username=username)

    def watch(self, username):
        if username not in active_users:
            return self.redirect('/')
        return self.render_template('watch.html', username=username)

@sio.event
def connect(sid, environ):
    print(f"Client {sid} connected")

@sio.event
def disconnect(sid):
    print(f"Client {sid} disconnected")

@sio.event
def stream(sid, data):
    username = data.get('username')
    frame = data.get('frame')
    sio.emit('broadcast', {'username': username, 'frame': frame}, skip_sid=sid)

def run_server():
    eventlet.wsgi.server(eventlet.listen(('0.0.0.0', 5000)), socketio.WSGIApp(sio, MyApp().wsgi_app))

if __name__ == '__main__':
    run_server()

