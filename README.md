# kiro-test-1-hosting-test

# Seeing the results

There is a bit of confusion in the way the results of all surveys submitted are shown. In order to see the results you need to include a token of an individual user in the url but the results shown are those of all survey participants for the survey that token applies to. This isn't 'broken' but it's certainly confusing.

## Getting the server started locally

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
