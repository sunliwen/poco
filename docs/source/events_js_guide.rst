Events API JS 集成操作指南
===========================


简明教程
---------

JsSdk Demo页面 http://search.tuijianbao.net/sdk/demo/

需要在页面底部包含下面两个js文件::

    <script type="text/javascript" language="javascript" charset="utf-8" src="http://search.tuijianbao.net/sdk/js/api-1.6.js"></script>
    <script type="text/javascript" language="javascript" charset="utf-8" src="http://search.tuijianbao.net/sdk/skin/ui-1.6.js"></script>


API调用简单范例::

    <script type="text/javascript" language="javascript" >
        // 开发时可设置debug=true，此时提供的是系统预设的模拟数据，仅供开发使用。
        // 在正式网站上，debug要设置为false
        var debug = true;
        var p = new _poco("<API Key>", "http://<api server prefix>/api/v1.6", debug);

        // 这些是共享参数，每次对服务器的调用都会传送这些参数。
        p.addSharedParams({'item_id': 'K8900',
                           'user_id': 'U123',
                           'amount': '6'});

        // 这是一个浏览商品页的事件。
        p.addEvent({"event_type": "ViewItem"});

        //这是一个用户下单事件
        p.addEvent({"type": "PlaceOrder", "order_id": "O123", "order_content": "I123,1.50,2|I250,15.50,1"});

        // 这是一个用户自定义的事件（自定义事件不能和系统内置的事件同名，详见Recommender JS API文档）
        p.addEvent({"event_type": "CustomEvt1", "purchasing_amount": 15.0});

        // 这两个是对推荐接口的请求
        p.addRecommender({"type": "AlsoViewed"});
        p.addRecommender({"type": "ByHotIndex", "hot_index_type": "viewed", "category_id": "C1", "brand": "B25"});

        // 推荐请求的结果会回调这里设置的接口
        p.invoke("pCallback");
    </script>


如何跟踪用户搜索事件
--------------------

为了统计热门关键词，统计用户搜索关键词之间以及与购买商品的相关性，需要跟踪记录用户的搜索事件。

需要在搜索结果页添加如下代码::

    假设本页面是"牛黄解毒丸"的搜索结果页，那么为了跟踪此次搜索事件，可添加如下代码
    var p = new _poco("<API Key>", "http://<api server prefix>/api/v1.6", debug);
    ... ...
    // 假设此次搜索没有指定分类，添加如下代码：
    p.addEvent({"event_type": "Search", "user_id": "U1", "categories": "null", "q": "牛黄解毒丸"})
    // 或者如果此次搜索指定了分类1233和1355，添加如下代码
    p.addEvent({"event_type": "Search", "user_id": "U1", "categories": "1233,1355", "q": "牛黄解毒丸"})
    ... ...
    p.invoke("pCallback");

如何跟踪用户点击搜索页链接事件
-------------------------------

为了分析搜索效果，统计用户搜索关键词之间以及与购买商品的相关性，还需要跟踪记录用户点击搜索链接的事件。

需要在搜索结果页添加如下代码::

        假设我们需要跟踪搜索结果页上的链接点击事件。这些链接的HTML代码如下：
        <div id="search-results">
            <ul>
                <li><a href="http://example.com/product-1.html" data-item_id="1" class="result-link">Search Result 001</a></li>
                <li><a href="http://example.com/product-2.html" data-item_id="2" class="result-link">Search Result 002</a></li>
            </ul>
        </div>

        因为我们需要知道被点击的链接指向的是哪个商品，所以我们在链接中添加了"data-item_id"属性，其值为相应商品的item_id值。

        然后我们加入如下JS代码。
        <script>
        var p = new _poco("<API Key>", "http://<api server prefix>/api/v1.6", debug);
        ... ...
        p.track_links("#search-results .result-link",
                      "SearchResult",
                      {"q": "贝亲", "page": "1"});
        ... ...
        </script>
        这次对track_links的调用将注册上面那些搜索链接的点击事件。因为我们是要跟踪的是搜索结果链接点击，所以link_type为"SearchResult"。我们还希望跟踪相应搜索所用的参数，所以将shared_params中设置q, categories和page两个参数。这样每一个链接的点击事件都会记录查询字符串，分类和搜索结果页的页码。
        当某个链接被点击后，它上面的data-item_id属性也会被搜集起来，作为事件参数的一部分。
        假如我们点击上面第一个链接，就会向服务器发送如下的事件内容：
        {"event_type": "ClickLink", "link_type": "SearchResult", "q": "贝亲", "page": "1", "item_id": "1", "categories": "123,12355"}


如何跟踪用户跟踪推荐结果
-------------------------

为了统计并改进推荐展示的效果，需要跟踪用户对推荐链接的点击。

需要在有推荐内容的页面添加如下代码::

    假设在本页面上有若干链接指向推荐的结果，这些链接都有一个class属性"recommendation-result"。
    <div id="recommendations">
        <a href="" class="recommendation-result" data-item_id="001">商品1</a>
        <a href="" class="recommendation-result" data-item_id="002">商品2</a>
    </div>


    那么为了跟踪对这些链接的点击，添加如下JS代码：
        <script>
        var p = new _poco("<API Key>", "http://<api server prefix>/api/v1.6", debug);
        ... ...
        p.track_links("#recommendations .recommendation-result",
                      "RecommendationResult",
                      {"req_id": "342-34243-3424-aaaa"});
        ... ...
        </script>
    注：req_id为返回的推荐结果JSON的一个字段。
    如果一个页面有几个不同区域，分别从不同的推荐获得结果，那么需要分别跟踪这些不同链接。


如何跟踪热门关键词点击事件
---------------------------

为了统计热门关键词的点击状况，需要在热门关键词链接上也添加跟踪事件。

具体做法类似"如何跟踪用户点击搜索页链接事件"一节。但有一些参数设置不同::

        <div id="hot-keywords">
            <ul>
                <li><a href="http://example.com/product-1.html" data-keyword="牛黄" class="keyword-link">牛黄</a></li>
                <li><a href="http://example.com/product-2.html" data-keyword="减肥" class="keyword-link">减肥</a></li>
            </ul>
        </div>
        注：这次我们需要搜集的是所点击链接对应的keyword，所以添加的是"data-keyword"属性。

        <script>
        var p = new _poco("<API Key>", "http://<api server prefix>/api/v1.6", debug);
        ... ...
        p.track_links("#hot-keywords .keyword-link",
                      "HotKeyword", {});
        ... ...
        </script>


如何跟踪分类列表页面访问事件
-----------------------------

为了完整地分析用户行为，为用户提供个性化的定制推荐服务，最好也记录用户访问的分类页面。

需要在分类列表页面添加如下跟踪代码::

    假设本页面的category id是 1255 -> 125505 （两级分类）
    var p = new _poco("<API Key>", "http://<api server prefix>/api/v1.6", debug);
    ... ...
    p.addEvent({"event_type": "ViewCategory", "user_id": "U1", "categories": "1255,125505"})
    ... ...
    p.invoke("pCallback");

