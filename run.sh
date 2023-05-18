#!/usr/bin/env bash

export TEMP=/tmp
for i in data
do
    mkdir -p ${i}
done

if [ ! -d momepy ]; then
    git clone https://github.com/anisotropi4/momepy.git
    ln -sf ../momepy/momepy src/momepy2
fi

if [ ! -d jay ]; then
    git clone https://github.com/anisotropi4/jay.git
fi

FILESTUB=network-model
if [ ! -s data/${FILESTUB}-simple.gpkg ]; then
    URI=https://github.com/openraildata/network-rail-gis/releases/download/20230317-01
    if [ ! -s data/${FILESTUB}.gpkg ]; then
        curl -Lo data/${FILESTUB}.gpkg ${URI}/${FILESTUB}.gpkg
    fi
    (cd jay; ./simplify.sh ../data/${FILESTUB}.gpkg)
    ln jay/output/${FILESTUB}-simple.gpkg data/${FILESTUB}-simple.gpkg
fi

FILESTUB=great-britain-rail
if [ ! -s data/${FILESTUB}-simple.gpkg ]; then
    URI=https://github.com/anisotropi4/magpie/blob/master/great-britain-rail.gpkg?raw=true
    if [ ! -s data/${FILESTUB}.gpkg ]; then
        curl -Lo data/${FILESTUB}.gpkg ${URI}/${FILESTUB}.gpkg
    fi
    (cd jay; ./simplify.sh ../data/${FILESTUB}.gpkg)
    ln jay/output/${FILESTUB}-simple.gpkg data/${FILESTUB}-simple.gpkg
fi

export USE_PYGEOS=0

if [ ! -s linetrack.gpkg ]; then
    ./src/trackcheck.py
fi

if [ ! -s outputx.gpkg ]; then
    ./src/gettrack.py
fi

if [ ! -s tiploc-location.gpkg ]; then
    ./src/tiploc-match.py
fi
