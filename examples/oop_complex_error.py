class DatabaseConnector:
    def __init__(self):
        self.connected = False
        
    def connect(self):
        self.connected = True
        
    def execute_query(self, query):
        if not self.connected:
            raise ConnectionError("Not connected to database")
        # Simulating a query execution error later down the line
        return self._internal_execute(query)
        
    def _internal_execute(self, query):
        parser = QueryParser()
        return parser.parse_and_run(query)

class QueryParser:
    def parse_and_run(self, query):
        ast = self._build_ast(query)
        executor = QueryExecutor()
        return executor.run(ast)
        
    def _build_ast(self, query):
        return {"type": "SELECT", "target": query.split()[1]}

class QueryExecutor:
    def run(self, ast):
        target = ast["target"]
        return self._fetch_data(target)
        
    def _fetch_data(self, target):
        return self._read_from_disk(target)
        
    def _read_from_disk(self, target):
        # Intentional error: TypeError by trying to concatenate string and NoneType
        data_block = "Block_"
        block_id = None
        result = data_block + block_id
        return result

class Application:
    def __init__(self):
        self.db = DatabaseConnector()
        
    def run(self):
        self.db.connect()
        self.process_user_request()
        
    def process_user_request(self):
        user_manager = UserManager(self.db)
        user_manager.get_user_info("alice")

class UserManager:
    def __init__(self, db):
        self.db = db
        
    def get_user_info(self, username):
        query = f"SELECT * FROM users WHERE username='{username}'"
        result = self.db.execute_query(query)
        return result

def main():
    app = Application()
    app.run()

if __name__ == "__main__":
    main()
