______________________________________
GUNICORN Section:

testing if gunicorn works after creating wsgi file:
- gunicorn --bind 0.0.0.0:8080 wsgi:app
- then on web browser, go to http://0.0.0.0:8080/hello


TODO:
- sudo vim /etc/systemd/system/addapi_server.service
- sudo systemctl start addapi_server
- sudo systemctl enable addapi_server
- sudo systemctl status addapi_server

If errors:
- sudo systemctl daemon-reload
- sudo systemctl start addapi_server


Anytime you made any changes to the addapi_server.py file, do:
- sudo systemctl restart addapi_server

______________________________________
NGINX Section:

Where the server configs is:
- sudo vim /etc/nginx/sites-available/apizoo-server
Link: 
- sudo ln -s /etc/nginx/sites-available/apizoo-server /etc/nginx/sites-enabled/
Check for errors:
- sudo nginx -t 
Restart Nginx
- sudo systemctl restart nginx

Look at error logs:
- sudo tail /var/log/nginx/error.log

______________________________________
Final Check:
go to:
http://34.133.163.39/addapi/hello
