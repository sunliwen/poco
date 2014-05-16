    *  Install Elasticsearch on the destination server
        * elasticsearch-1.0.1.deb (You may also download it from ES site)

    * copy /usr/share/elasticsearch/plugins to the same directory on destination server

    * check /etc/elasticsearch/elasticsearch.yml for "path.data"
        * copy the directory of "path.data" on the source server to destination server
        * config "path.data" to the place of data on that server

    * restart ES server on destination server
