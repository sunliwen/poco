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


Analysis
--------
http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/analysis.html
    * Analyzer configuration

    * Analyzers
        * Analyzers are composed of a single Tokenizer and zero or more TokenFilters
        * The tokenizer may be preceded by one or more CharFilters

    * custom analyzer
        * http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/analysis-custom-analyzer.html

    * language analyzers
        * http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/analysis-lang-analyzer.html

    * Tokenizer
        * Tokenizers are used to break a string down into a stream of terms or tokens
        * http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/analysis-tokenizers.html

    * TokenFilter

    * CharFilter
        * http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/analysis-charfilters.html


Index Configuration
-------------------
analyze:
    http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/indices-analyze.html

Config
    * Index aliases
        * http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/indices-aliases.html

Mapping
    * Field names with the same name across types are highly recommended to have the same type and same mapping characteristics (analysis settings for example)
    * fields: http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/mapping-fields.html
    * types: http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/mapping-types.html

Query
-----
    * common options http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/common-options.html
        * fuzziness
    * Query DSL
        * match query http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/query-dsl-match-query.html
            * default match type is of type boolean: analyzed and construct a boolean query. operator can be "or" or "and"
                * minimum_should_match
            * match_phrase
            * match_phrase_prefix
        * multi_match http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/query-dsl-multi-match-query.html            * match multiple fields.
        * queries which combine other queries
            * bool query
                * A query that matches documents matching boolean combinations of other queries
            * boosting query
        * common terms query http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/query-dsl-common-terms-query.html
            * The common terms query divides the query terms into two groups: more important (ie low frequency terms) and less important (ie high frequency terms which would previously have been stopwords).
        * filtered query http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/query-dsl-filtered-query.html
        * fuzzy like this query http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/query-dsl-flt-query.html
        * function score query http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/query-dsl-function-score-query.html
            * calculate a new score for the query result
        * fuzzy http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/query-dsl-fuzzy-query.html
        * more like this http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/query-dsl-mlt-query.html
        * prefix query http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/query-dsl-prefix-query.html
        * range query http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/query-dsl-range-query.html
        * regex query http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/query-dsl-regexp-query.html
            * similiar query: wildcard query http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/query-dsl-wildcard-query.html
        * span queries (???) http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/query-dsl-span-first-query.html
        * term query http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/query-dsl-term-query.html
            * Matches documents that have fields that contain a term (not analyzed)
        * terms query
            * A query that match on any (configurable) of the provided terms.

    * Filters
        * should be used for: binary yes/no searches; on exact queries
        * quick and also a great candidate for caching
        * Note: price range can use "range filter"

    * fields http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/search-request-fields.html
        * selectively load specific stored fields

    * highlighter http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/search-request-highlighting.html
    * rescoring http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/search-request-rescore.html
        * Rescoring can help to improve precision by reordering just the top (eg 100 - 500) documents returned by the query and post_filter phases, using a secondary (usually more costly) algorithm
    * search type http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/search-request-search-type.html


Percolator (??)
---------------
http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/search-percolate.html

More like this
--------------
http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/query-dsl-mlt-query.html

Facet vs. Aggregations
----------------------
http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/search-aggregations.html


prefix queries and ngrams  (TODO: check)
----------------------------------------

Analyzer/Filter/Tokenizer/Payloads
---------------
    index_analyzer search_analyzer


Did you mean
------------
    * Suggester is often called “Did you mean” functionality.
        * Use Phrase suggester http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/search-suggesters-phrase.html


Complete Me
-----------
    * use completion suggester http://www.elasticsearch.org/blog/you-complete-me/
    * multiple inputs
    * working with synonyms
        * 
    * it will often make more sense to maintain the suggestions in a separate index
    * Improving relevance
        * Log your searches, find the most important ones, add good suggestions first
        * Log the suggestions which were selected by the user (together with the searches)
        * Refine your inputs based on the above steps
        * Use weights with a reasonable logic behind them – one which adheres to your revenue model or whatever your definition of a best result is
    * fuzzy

Suggestion
----------
implement jd.com style autocompletion
term facets?

1. Match stored query strings.
    * use leyou's server log
    * How leyou's popular query string are generated?
    * use term facets? combined with category+brand
    store query string/popularity/results count

maybe use facet?

category+brand+common terms

if you enter a term, some other terms which may further narrow down 

suggest corrections

Search Suggesters
-----------------
http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/search-suggesters.html
    * Several Suggestions can be specified per request
    * And a global suggest text can be used.

http://elasticsearchserverbook.com/elasticsearch-0-90-using-suggester/

Term Suggester
http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/search-suggesters-term.html
    * The terms suggester allows to fetch suggestions for given word
    * default suggest mode: missing


两种Python Library
------------------


生产环境更改Mapping
-------------------
http://donlianli.iteye.com/blog/1924721
用alias index.


Types
------
Multi_field


Sites & Documents
-----------------
    * http://elasticsearchserverbook.com/
