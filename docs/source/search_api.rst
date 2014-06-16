Search API
==========

路径: /v1.6/public/search/

HTTP方法: GET/POST

传入参数
---------

=============    ==========  ==========================================================   =============================================
参数名           是否必填    默认值                                                       描述                                         
=============    ==========  ==========================================================   =============================================
q                是                                                                       用户输入的查询内容。目前搜索的字段包括：item_name, description, brand, tags和sku。sku为完全匹配。
page             否          1                                                            返回查询结果的页码                           
per_page         否          20                                                           返回查询结果中每页结果数
sort_fields      否          [] (根据搜索结果相关度排序)                                  根据哪些字段排序。升序：直接填写字段名;降序：在字段名前加"-"。                                                                                                                                
filters          否          []                                                           根据哪些字段值来过滤结果（具体见下面的示例）
facets           否                                                                       对返回的聚类结果进行配置。categories配置参见下面注解。
highlight        否          False                                                        是否在结果中加亮标记匹配的关键词
search_config    否          {"type": "SEARCH_TEXT"}                                      详见下面注解。
api_key          是                                                                       分配给用户站点的api key
=============    ==========  ==========================================================   =============================================

注::

    1. filters:
        1. "categories"字段只接受0或1个值，不接受多个值。
        2. 实施过程中，需要确定哪些字段用来过滤。目前，price, market_price, categories，item_id、available、item_level、item_comment_num和origin_place可用来过滤。
        3. available 默认为[true]，即如果不在filter中指定available，则仅仅返回有售的产品。
    2. sort_fields:
        1. price、market_price、item_level、item_comment_num和origin_place可用来排序。
    3. facets (聚类)
        1. 如果在传参中没有此参数，则为默认状态。默认状态所有支持的facets都选中,categories为"SUB_TREE"模式
        2. 如果在传参中指定"facets"，则仅返回制定的聚类::
           {"brand": {}}  # 这样仅返回brand的聚类
           {"brand": {}, "origin_place": {}} # 这样仅聚合brand和origin_place
           {"categories": {"mode": "DIRECT_CHILDREN"}} # 如果在filters中指定分类，则聚合这些分类的直接子分类；如果在filters中未指定分类，则聚合所有顶层分类
           {"categories": {"mode": "SUB_TREE"}} # 如果在filters中指定分类，则聚合这些分类及其所有直接间接子类；如果在filters中未指定分类，则聚合所有分类
    4. search_config
        1. 全文搜索：type=SEARCH_TEXT，示例
            {"type": "SEARCH_TEXT"}
        2. 标签匹配：type=SEARCH_TERMS
            选择这种搜索时，要匹配的标签放到q之中，标签间以空格分隔。
            所有标签必须匹配
            {"type": "SEARCH_TERMS",
             "match_mode": "MATCH_ALL",
             "term_field": "tags"}

            可部分匹配标签，匹配越多的排序靠前
            {"type": "SEARCH_TERMS",
             "match_mode": "MATCH_MORE_BETTER",
             "term_field": "tags"}


返回结果
---------

==============    ===============================
名称               说明
==============    ===============================
records            搜索到的产品
info               包含和此次结果相关的一系列信息，详见示例。
info["facets"]     info中的facets包含在事先配置好的若干维度上的聚类结果，详见示例。
errors             错误信息。正常情况下为[]。
==============    ===============================

注：
    1. info["facets"]中，
       a. "categories"部分返回的是目前选定分类的子分类（或顶级分类，如果没有分类选定）的结果数;
       b. 另外还支持brand和origin_place的聚类。

示例
-----

注：
    1. 请使用相应站点的api_key

请求::

    curl -X GET 'http://poco.tuijianbao.net/api/v1.6/public/search/' \
         -H 'Content-Type: application/json' \
         -d '{
            "api_key": "123456",
            "q": "bb",
            "sort_fields": ["-price", "-market_price"],
            "page": 1,
            "highlight": true,
            "filters": {
                "categories": ["17"],
                "price": {
                    "type": "range",
                    "from": 15.00,
                    "to": 150.00
                }
            }
         }'

说明：
    1. filters: price是根据范围过滤。

结果::

    {
        "records": [{
                "item_id": "FA123355",
                "item_name": "贝亲",
                "categories": [1255, 125588]
                "price": 12.50,
                "image_link": "http://example.com/images/123456.jpg",
                "item_link":  "http://example.com/products/1233/"
            }],
        "info": {
                "current_page": 1,
                "num_pages": 5,
                "per_page": 20,
                "total_result_count": 100,
                "facets": {
                    "categories": [
                        {"label": "饮料", "id": "2255", "count": 15}
                        {"label": "童装", "id": "3721", "count": 8}
                        ],
                    "brand": [
                        {"label": "雀巢", "id": "1000", "count": 25,
                         "label": "贝亲", "id": "3800", "count": 15}
                    ],
                    "origin_place": [
                        {"label": "", "id": "0", "count": 10,
                         "label": "", "id": "1", "count": 5}
                    ]
                }
            },
        "errors": []
    }

说明：
    1. current_page: 当前结果页页码
    2. num_pages: 搜索结果总页数
    3. per_page: 每页有多少结果
    4. total_result_count: 搜索结果总数
    5. facets: 示例中的facets是显示在搜索结果中，包含哪些不同分类（category），各分类有多少搜索结果。
