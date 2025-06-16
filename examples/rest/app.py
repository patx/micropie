from micropie_rest import RESTApp, route

class MyApp(RESTApp):

    @route("/api/users/{user:str}/records/{record:int}", method=["GET", "HEAD"])
    async def _get_record(self, user: str, record: int):
        return {"user": user, "record": record}
    
    @route("/api/users/{user:str}/records", method=["POST"])
    async def _create_record(self, user: str):
        try:
            data = self.request.get_json
            return {"user": user, "record": data.get("record_id"), "created": True}
        except Exception:
            return {"error": f"Invalid JSON"}
    
    @route("/api/users/{user:str}/records/{record:int}/details/subdetails", method="GET")
    async def _get_record_subdetails(self, user: str, record: int):
        return {"user": user, "record": record, "subdetails": "more detailed info"}
    
    # Implicitly routed (not using decorator)
    async def records(self, user: str, record: str):
        try:
            record_id = int(record)
            return {"user": user, "record": record_id, "implicit": True}
        except ValueError:
            return {"error": "Record must be an integer"}
    
    # Private route, not exposed
    async def _private(self):
        return {"viewing": "private"}

app = MyApp()
