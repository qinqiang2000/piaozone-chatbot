#! /bin/bash 
#kill -9 $(netstat -nlp | grep :9999 | awk '{print $7}' | awk -F"/" '{ print $1 }')
sudo netstat -tulnp | grep ':9999' | awk '{print $7}' | cut -d'/' -f1 | xargs -r sudo kill

source venv/bin/activate

git pull

nohup python src/app.py >> run.log  2>&1 &

#tailf run.log
