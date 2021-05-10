[![Discord](https://discordapp.com/api/guilds/748687781605408908/widget.png?style=shield)](https://discord.gg/ShEQgUx)

Installation Guide
-------------
important notes:
- ubuntu 20.04 & nginx have unknown issues? i recommend using 18.04
- i will not help with the creation of a fake *.ppy.sh cert for switcher support.

```sh
# add ppa for py3.9 (required since it's new)
sudo add-apt-repository ppa:deadsnakes/ppa

# install requirements (py3.9, mysql, nginx, build tools, certbot)
sudo apt install python3.9 python3.9-dev python3.9-distutils \
                 mysql-server nginx build-essential certbot

# install pip for py3.9
wget https://bootstrap.pypa.io/get-pip.py
python3.9 get-pip.py && rm get-pip.py

# clone the repo & init submodules
git clone https://github.com/circles-fun/circles.git && cd circles
git submodule init && git submodule update

# install circles requirements w/ pip
python3.9 -m pip install -r ext/requirements.txt

# build oppai-ng's binary
cd oppai-ng && ./build && cd ..

######################################
# NOTE: before continuing, create an #
# empty database in mysql for circles  #
######################################

# import circles's mysql structure
mysql -u your_sql_username -p your_db_name < ext/db.sql

# generate an ssl certificate for your domain (change email & domain)
sudo certbot certonly \
    --manual \
    --preferred-challenges=dns \
    --email your@email.com \
    --server https://acme-v02.api.letsencrypt.org/directory \
    --agree-tos \
    -d *.your.domain

# copy our nginx config to `sites-enabled` & open for editing
sudo cp ext/nginx.conf /etc/nginx/sites-enabled/circles.conf
sudo nano /etc/nginx/sites-enabled/circles.conf

##########################################
# NOTE: before continuing, make sure you #
# have completely configured the file.   #
##########################################

# reload the reverse proxy's config
sudo nginx -s reload

# copy our circles config to cwd & open for editing
cp ext/config.sample.py config.py
nano config.py

##########################################
# NOTE: before continuing, make sure you #
# have completely configured the file.   #
##########################################

# start the server
./main.py
```

Directory Structure
------
    .
    ├── constants  # code representing gamemodes, mods, privileges, and other constants.
    ├── ext        # external files from circles's primary operation.
    ├── objects    # code for representing players, scores, maps, and more.
    ├── utils      # utility functions used throughout the codebase for general purposes.
    └── domains    # the route-continaing domains accessible to the public web.
        ├── cho    # (ce|c4|c5|c6).ppy.sh/* routes (bancho connections)
        ├── osu    # osu.ppy.sh/* routes (mainly /web/ & /api/)
        └── ava    # a.ppy.sh/* routes (avatars)
