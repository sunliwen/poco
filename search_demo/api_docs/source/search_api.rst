搜索API
==========

路径: /v1.6/search/

HTTP方法: POST

传入参数
---------

=============    ==========  ===============================   =============================================
参数名           是否必填    默认值                            描述                                         
=============    ==========  ===============================   =============================================
q                是                                            用户输入的查询内容                           
page             否          1                                 返回查询结果的页码                           
sort_fields      否          [] (根据搜索结果相关度排序)       根据哪些字段排序。升序：直接填写字段名;降序：在字段名前加"-"。                 
filters          否          []                                根据哪些字段值来过滤结果（具体见下面的示例）
api_key          是                                            分配给用户站点的api key
config_key       是                                            本次搜索所使用的配置（配置在Dashboard中进行）
=============    ==========  ===============================   =============================================

返回结果
---------

==============    ===============================
名称               说明
==============    ===============================
records            搜索到的产品
info               包含和此次结果相关的一系列信息，详见示例。
info["facets"]     info中的facets包含在事先配置好的若干维度上的结果数，详见示例。
errors             错误信息。正常情况下为{}。
==============    ===============================

示例
-----

注：
    1. 示例中的参数仅供参考，并非可以直接用于另行提供的测试站点实例
    2. 请使用相应站点的api_key和config_key

请求::

    curl -X POST 'https://<sub_domain>.tuijianbao.net/v1.6/search/' \
         -H 'Content-Type: application/json' \
         -d '{
            "api_key": "<分配给用户站点的api key>",
            "q": "奶粉",
            "sort_fields": ["categories", "-brands"],
            "page": 2,
            "filters": {
                "categories": [102233],
                "brands": [3721],
                "price": {
                    "type": "range",
                    "from": 3.00,
                    "to": 15.00
                }
            },
            "config_key": "<本次搜索所用后台配置的key>"
         }'

结果::

    {
        "records": [{
                "item_id": "FA123355",
                "item_name": "贝亲",
                "categories": [1255, 3721]
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
                        {"label": "饮料", "id": 2255, "count": 15}
                        {"label": "童装", "id": 3721, "count": 8}
                        ]
                }
            },
        "errors": {}
    }

说明：
    1. current_page: 当前结果页页码
    2. num_pages: 搜索结果总页数
    3. per_page: 每页有多少结果
    4. total_result_count: 搜索结果总数
    5. facets: 示例中的facets是显示在搜索结果中，包含哪些不同分类（category），各分类有多少搜索结果。
