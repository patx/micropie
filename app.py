from MicroPie import Server

class root(Server):

    def static(self, filename):
        return self.serve_static(filename)

    def index(self):
        return 'hello world'

root().run()
