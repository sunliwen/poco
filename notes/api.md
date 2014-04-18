## Overview

There will be public and private APIs. The key difference are if the API should be exposed to internet. Eg: the data to serve the requests from javascript code in browser. Including tracking events and retieving recommendation data, those APIs will be required to be public accessable.

### Public APIs - `/public`

Mainly to serve requests from javascript codes in browser. Should apply limit rates to protect the services from abuse (but this might not be necessary).

Those APIs are mainly readonly, except ｀/events`.

* `/public/search`
* `/public/suggest`
* `/public/recommender`
* `/public/events`

### Private APIs - `/private`

To provide more powerful, APIs

## APIs

* `/private/search`
* `/private/suggest`
* `/private/recommender`
* `/private/items` or `/private/properties`
* `/private/users`
* `/private/users/:id/orders`
* `/private/orders/:id`
* `/private/events`
* `/private/properties`


### `/search`

* `GET /search?q=xxxxx`

* 产品搜索功能
* 基于Lucene/ElasticSearch


### `/suggest`

* `GET /suggest`


### `/units`

* 离线计算
* 根据不同场景定义ad unit
* 定义不同的unit


### `/categories`

* `GET /categories`
* `GET /categories/:id`

### [pending]`/items`

* `GET /items`
* `GET /items/:id`

获取商品及基于商品获取相关性推荐。

### [pending]`/users`

* `GET /users`
* `GET /users/:id`


### [pending]`/orders` & `/line_items`

* `GET /orders`
* `GET /orders/:id`
* `GET /orders/:id/line_items`
* `GET /line_items/:id`

## [pending]Terms

* ad unit - 单元，一段逻辑来定义一个数据输出
* placements - 位置，一个位置（eg: div）用来显示数据输出
* custom targeting - 用户定位，通过某些特征（eg: 属性、行为）来确定用户。



## [pending]Trafficking and inventory



## [pending]TODO

* [privacy] 添加条款说明：不允许传送能用来识别个人身份的数据。
*



## Properties (eg: Product, Category, Brand, etc.)


Every property will have a $type, which will be used to route for different property processors.
And each property could be updated by id.

The problem will occur is there are hierarchy relationships between `category`.
And If they are embedded in `project`, once the relationship changed, the cost is high to update all the `projects`.
But this is actually the problem of the user who maintain the data posted to us, not really a problem with the search engine.


```
property: {
    $type:'product',
    $id:123,
    $name:'产品123',
    categories:[
        {
            $type:'category',
            $id:123,
            $name:'分类1',
            $parent_id:0
        },
        {
            $type:'category',
            $id:234,
            $name:'分类2',
            $parent_id:123
        },
        {
            $type:'category',
            $id:345,
            $name:'分类3',
            $parent_id:234
        }
    ],
    brand:{
        $type:'brand',
        $id:123,
        $name:'品牌1'
    }
}



property: {
    $type:'category',
    $id:123,
    $name:'分类1',
    $parent_id:0
},
```
