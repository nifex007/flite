# Flite


### SET UP APP WITH DOCKER

This assumes you have docker installed. <br>Run these commands below in your terminal in the directory where `Dockerfile` and `docker-compose.yml` can be found.

```bash
cd flite
# rename .env.example to .env
mv .env.example .env
source .env
docker-compose up
````


### API Documentation
https://www.getpostman.com/collections/1a1049d53dd560f75aff


## Test

`sudo docker-compose run django python manage.py test `

### Assumptions 

* Balance model are used as accounts 
* Same transaction reference for p2p transfers used differentiating values are (transaction_type(debit, credit), user)