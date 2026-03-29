# kiro-test-1-hosting-test

After initial ...
```
docker compose up
```
it's necessary to create a superuser
```
docker compose exec web python manage.py createsuperuser
```
after that the admin login access can be accessed at 
```
http://localhost:8000
```
