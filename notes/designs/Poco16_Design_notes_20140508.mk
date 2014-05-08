
Recommender JS API
===================
Check http://search.tuijianbao.net/docs/v1.6/recommender/recommender_js_api.html

Custom Events
^^^^^^^^^^^^^^
To implement custom events, we just let the api accept other 'event_type's which is not reserved by our system. 
    * For reserved types, the schema would be validated.
    * For custom types, only required params are checked (event_type, user_id, api_key)

Ad Units
========
The custom ad units does not cause incompatible changes for js api. Now the client can call::

    p.addRecommender({"type": "/unit/home"})

to get data from ad units.


Recommender API - Server Side
==============================
On the server side, the built-in recommenders and custom ad unit would registered like this::
    
    # built-in recommender types. directly map them to a underly recommender processor
    rec_unit.register("ByBrowsingHistory", ByBrowsingHistoryProcessor)
    rec_unit.register("ByHotIndex", ByHotIndexProcessor)
    
    # And ad units which combine other built-in processors
    # The argument processor defines which params are required for this unit
    rec_unit.register("/unit/home", 
                      IfEmptyTryNextProcessor(
                         ArgumentProcessor(
                            "user_id": True
                         ),
                         [{"type": "ByBrowsingHistory"},
                          {"type": "ByHotIndex", "hot_index_type": "viewed"}])
                      )


Item Indexing
=============
Every time, an item or a batch of items are posted to our server, an item posting task (recommender.tasks.process_item_update_queue) would be added to Celery. It would:
    1. update items to mongodb
    2. update properties (of brand/categories) contained in the item to properties collection
    3. index the item to ES
        * while indexing the item, the keywords in the item name would be splitted. The unidentified keywords would be recorded in mongodb.


Extraction of Suggestion Keywords White List
=============================================
    1. Run 'python manage.py runscript extract_unidentified_keywords --script-args=<site_id> <file_path>' to extract unidentified keywords recorded.
    2. Prefix '#' to lines which should be black listed. 
    3. After finished the identification work, run 'python manage.py runscript upload_identified_keywords --script-args=<site_id> <file_path>'

Dependency on Poco 1.0 code
============================
    * Batch calculation of statistics/similarities ; Dashboard; Admin Board
    * And there are changes to Poco 1.0 code. poco_1.6 branch should be used instead of the 'master' branch.

Current Dependencies on Services
=================================
    - ElasticSearch
    - MongoDB
    - RabbitMQ / Celery
    - Redis
    - PostgresSQL
