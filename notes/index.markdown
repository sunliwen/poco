ElasticSearch Configuration
---------------------------
Use G1 garbage collection
http://donlianli.iteye.com/blog/1948787

elasticsearch配置文件


Index Creation/Configuration
----------------------------

Sharding/Replicas
-----------------


Bulk Update (TODO)
-----------


Facet (TODO)
------------


Store & Index property
----------------------
http://donlianli.iteye.com/blog/1975727

Install Plugins
---------------
http://www.dengchuanhua.com/212.html


http://s.medcl.net/
-------------------


Search API
----------
    * http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/search-search.html
    * query string query / request body

    request body search (TO Continue ...)



stats groups
    * get popular query use this? http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/search.html#stats-groups

Index Versioning
    * http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/docs-index_.html

Multiple indices
----------------
    * http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/multi-index.html


Different Way of API Connection
-------------------------------
    * Http http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/modules-http.html
        * use Http keep alive
    * Or Thrift
        * http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/modules-thrift.html


联想输入/Pinyin
---------------

http://www.elasticsearch.cn/

结果聚合
    * https://github.com/medcl/elasticsearch-carrot2

partial update
    * https://github.com/medcl/elasticsearch-partialupdate

简/繁转换
    * https://github.com/medcl/elasticsearch-analysis-stconvert

string2int
    * https://github.com/medcl/elasticsearch-analysis-string2int

分词。等。
TODO: http://donlianli.iteye.com/blog/1923017

smartcn
https://github.com/elasticsearch/elasticsearch-analysis-smartcn

多种分词：
    * 见elasticsearch-rtf
        * https://github.com/medcl/elasticsearch-analysis-mmseg
        * https://github.com/4onni/elasticsearch-analysis-ansj
        * jieba

TODO
IK中文分词
http://donlianli.iteye.com/blog/1948841
https://github.com/medcl/elasticsearch-analysis-ik
    * 自定义词典

如何将分词和拼音一起用

TODO
同义词
http://bbs.elasticsearch.cn/discussion/170/elasticsearch-synonym-%E6%80%8E%E4%B9%88%E4%BD%BF%E7%94%A8-%E5%9C%A8yml%E9%87%8C%E9%85%8D%E7%BD%AE%E4%BA%86%E4%BD%86%E6%98%AF%E4%B8%8D%E5%85%B6%E6%95%88%E6%9E%9C-yml-%E9%85%8D%E7%BD%AE%E5%A6%82%E4%B8%8B/p1里面还有如何用filter。多个filter


两种Python Library
------------------


生产环境更改Mapping
-------------------
http://donlianli.iteye.com/blog/1924721
用alias index.


Types
------
Multi_field
