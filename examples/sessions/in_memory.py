from MicroPie import App

class MyApp(App):
    async def index(self):
        # Use self.request.session to access the session data.
        if "visits" not in self.request.session:
            self.request.session["visits"] = 1
        else:
            self.request.session["visits"] += 1
        return f"You have visited {self.request.session['visits']} times."

app = MyApp()
