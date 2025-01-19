# Deploying MicroPie with Gunicorn

This guide explains how to run the **MicroPie** framework with **Gunicorn**, a high-performance WSGI server, for improved concurrency and scalability.


## **1. Install Dependencies**

Ensure you have Python and `pip` installed, then install the required dependencies:

```bash
pip install micropie gunicorn
```


## **2. Create a MicroPie Application**

Create a file named `server.py` with the following content:

```python
from MicroPie import Server

class MyApp(Server):
    def index(self, name="Guest"):
        return f"Hello, {name}! Welcome to MicroPie."

# Create an instance of the app
app = MyApp()
```


## **3. Run MicroPie with Gunicorn**

Start the server using Gunicorn with multiple worker processes for better performance:

```bash
gunicorn -w 4 -b 127.0.0.1:8080 server:app
```

### **Explanation of the command:**
- `-w 4`: Number of worker processes (adjust based on CPU cores; recommended `2 * cores + 1`).
- `-b 127.0.0.1:8080`: Binds the application to localhost on port 8080.
- `server:app`: Refers to `server.py` and the instance `app` inside it.

Visit your app at [http://127.0.0.1:8080](http://127.0.0.1:8080).


## **4. Running with Different Worker Types**

Gunicorn supports different worker models for various workloads:

### **1. Sync Workers (Default)**
```bash
gunicorn -w 4 -b 127.0.0.1:8080 server:app
```

### **2. Threaded Workers (For I/O-bound tasks)**
```bash
gunicorn -w 4 --threads 2 -b 127.0.0.1:8080 server:app
```

### **3. Gevent Workers (Asynchronous handling)**
Install Gevent first:
```bash
pip install gevent
```
Run with:
```bash
gunicorn -w 4 -k gevent -b 127.0.0.1:8080 server:app
```


## **5. Running Gunicorn in Daemon Mode**

To run Gunicorn in the background with logging enabled:

```bash
gunicorn -w 4 -b 0.0.0.0:8080 server:app --daemon --access-logfile access.log
```

To stop the server:

```bash
pkill gunicorn
```


## **6. Deploying with Nginx as a Reverse Proxy**

For production, it's recommended to use **Nginx** as a reverse proxy to handle incoming traffic.

### **Steps to configure Nginx:**

1. Install Nginx:

   ```bash
   sudo apt install nginx
   ```

2. Add an Nginx configuration file (`/etc/nginx/sites-available/micropie`):

   ```nginx
   server {
       listen 80;
       server_name yourdomain.com;

       location / {
           proxy_pass http://127.0.0.1:8080;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
       }
   }
   ```

3. Enable the configuration and restart Nginx:

   ```bash
   sudo ln -s /etc/nginx/sites-available/micropie /etc/nginx/sites-enabled
   sudo systemctl restart nginx
   ```

Now your MicroPie app will be accessible via your domain.


## **7. Monitoring Gunicorn Performance**

Check running Gunicorn processes:

```bash
ps aux | grep gunicorn
```

Reload Gunicorn without downtime:

```bash
gunicorn --reload -w 4 -b 127.0.0.1:8080 server:app
```

## **8. Conclusion**

Running MicroPie with Gunicorn provides:

- Better concurrency and scalability.
- Improved reliability and fault tolerance.
- Easy integration with Nginx for production deployment.

By following this guide, you can ensure your MicroPie application is production-ready and performs efficiently.
