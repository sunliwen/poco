Create Index/Load Data
----------------------
source code: poco/scripts/load_data.py
    createIndex function
        item_name is a multi_field.
        All analyzer/tokenizer/filter are defined here.

        The Chinese segmentation are currently done by Python jieba library instead of the jieba plugin of elasticsearch. It is because of I've failed to get jieba plugin's filter/tokenizer work. The semented item_name would be sent to elasticsearch, and analyzed use a whitespace/pinyin tokenizer.


Search/Query String Suggestion
------------------------------
source code: poco/main_app/view.py
    * check def construct_query for how the query is constructed. The query boost Chinese matching.
    * v_ajax_auto_complete_term
        * This is the auto completion
        * check _getQuerySuggestions for facets


Libraries
----------
elasticsearch
    * http://elasticsearch-py.readthedocs.org/en/master/

elasticutils
    * This one is easier to use.
    * http://elasticutils.readthedocs.org/en/latest/

pinyin elasticsearch plugin
    * https://github.com/medcl/elasticsearch-analysis-pinyin
