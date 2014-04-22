Items API
==========

路径: /v1.6/private/items/

HTTP方法: POST

功能：
    用来推送/更新商品信息。

传入参数
---------

传入参数为一个JSON结构，包括api_key和商品信息字段。目前可传如下字段：

================  ==========  ===============================   =============================================
参数名            是否必填    默认值                            描述                                         
================  ==========  ===============================   =============================================
type              是                                            目前仅支持类型："product"                    
item_id           是                                            商品的ID                                     
available         否          true                              此商品是否有售
item_link         是                                            商品的链接
item_name         是                                            商品名称
description       否                                            商品描述
image_link        否                                            商品图片链接
price             否                                            商品价格
market_price      否                                            商品市场价
categories        否          []                                商品分类。详细结构见下面注释
brand             否                                            商品品牌。详细结构见下面注释
item_level        否                                            商品星级。类型：数字
item_spec         否                                            规格文字
item_comment_num  否                                            商品评论数。类型：数字
origin_place      否                                            商品产地
api_key           是                                            分配给用户站点的api key
================  ==========  ===============================   =============================================

注：
    1. categories中的元素结构如下::

        { "type": "category",
          "id": "<分类ID>",
          "name": "<分类名称>",
          "parent_id": "<父分类ID>"
        }
        假设一个商品属于如下分类 "中西药品 > 呼吸道系统 > 清肺药"，这三个分类的ID分别是2, 11, 544
        则categories应该如下：
        [
            {"type": "category",
             "id": "2",
             "name": "中西药品",
             "parent_id": "null"
            },
            {"type": "category",
             "id": "11",
             "name": "呼吸道系统",
             "parent_id": "2"
            },
            {"type": "category",
             "id": "544",
             "name": "清肺药",
             "parent_id": "11"
            }
        ]
        当一个分类为顶级分类时，其"parent_id"应该设置为"null"。

    2. brand中的元素结构如下::

        { "type": "brand",
          "id": "<品牌分类>",
          "name": "<品牌名称>"
        }

返回结果
---------

==============    ===============================
名称               说明
==============    ===============================
code              0 - 操作正确完成；1 - 参数有误; 99 - 未知服务器错误。
err_msg           code非0时，错误信息
==============    ===============================

示例
-----

注：
    1. 请使用相应站点的api_key

请求::

    curl -X POST 'http://search.tuijianbao.net/api/v1.6/private/items/' \
         -H 'Content-Type: application/json' \
         -d '{
            "api_key": "<THE API KEY>",
            "type": "product",
            "item_id": "I123",
            "item_name": "产品123",
            "item_link": "",
            "brand": {
                "type": "brand",
                "id": "22",
                "name": "雀巢",
            },
            "item_level": 5,
            "item_comment_num": 15,
            "categories": [
                {
                    "type": "category",
                    "id": "123",
                    "name": "分类1",
                    "parent_id": "null"
                },
                {
                    "type": "category",
                    "id": "234",
                    "name": "分类2",
                    "parent_id": "123"
                }
            ]
         }'


结果::

    {
        "code": "0"
    }

