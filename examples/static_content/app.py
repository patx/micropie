from MicroPie import Server

class Root(Server):

    def static(self, filename):
        return self.serve_static(filename)


app = Root()
