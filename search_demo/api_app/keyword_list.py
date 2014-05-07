import redis
from django.conf import settings
from api_app import es_search_functions
from common.mongo_client import getMongoClient


class KeywordList:
    WHITE_LIST = "W"
    BLACK_LIST = "B"
    UNIDENTIFIED_LIST = "U"

    def __init__(self, es, mongo_client):
        self.es = es
        self.mongo_client = mongo_client
        self.redis_client = redis.StrictRedis(host=settings.REDIS_CONFIGURATION["host"], 
                                              port=settings.REDIS_CONFIGURATION["port"], 
                                              db=settings.REDIS_CONFIGURATION["db"])

    def getKeywordListRedisKey(self, site_id):
        return "suggestion-keyword-list-%s" % site_id

    def prefillCache(self, keyword_list_key, site_id):
        keyword_list = {}
        for record in self.mongo_client.getSuggestKeywordList(site_id):
            keyword_list[record["keyword"]] = record["type"]
        if len(keyword_list) > 0:
            self.redis_client.hmset(keyword_list_key, keyword_list)

    def getKeywordStatus(self, site_id, keyword):
        keyword_list_key = self.getKeywordListRedisKey(site_id)
        # TODO: optimize this
        if not self.redis_client.exists(keyword_list_key):
            self.prefillCache(keyword_list_key, site_id)
        
        keyword_status = self.redis_client.hget(keyword_list_key, keyword)
        return keyword_status

    # return accepted_keywords and update unidentified keywords to db.
    def processKeywords(self, site_id, keywords):
        accepted_keywords, to_be_in_unidentified_keywords = [], []
        for keyword in keywords:
            keyword_status = self.getKeywordStatus(site_id, keyword)
            if keyword_status == self.WHITE_LIST:
                accepted_keywords.append(keyword)
            elif keyword_status == None:
                to_be_in_unidentified_keywords.append(keyword)
        self._updateUnidentifiedKeywords(site_id, to_be_in_unidentified_keywords)
        return accepted_keywords

    def updateSuggestKeywordList(self, site_id, list_type, keywords):
        self.mongo_client.updateSuggestKeywordList(site_id, list_type, keywords)
        keyword_list = {}
        for keyword in keywords:
            keyword_list[keyword] = list_type
        if len(keyword_list) > 0:
            self.redis_client.hmset(self.getKeywordListRedisKey(site_id), keyword_list)

    def _updateUnidentifiedKeywords(self, site_id, to_be_in_unidentified_keywords):
        self.updateSuggestKeywordList(site_id, self.UNIDENTIFIED_LIST, 
                to_be_in_unidentified_keywords)


    def _indexKeywordsForCompletion(self, site_id, keywords):
        res = self.es.indices.analyze(index=es_search_functions.getESItemIndexName(site_id), 
                                text=" ".join(keywords),
                                analyzer="mycn_analyzer_whitespace_pinyin_first_n_full")
        for token_idx in range(len(res["tokens"])):
            token = res["tokens"][token_idx]
            raw_keyword = keywords[token_idx]
            splitted_token = token["token"].split("||")
            first_letters = splitted_token[0]
            full_pinyin = "".join(splitted_token[1:])
            result = {"keyword_completion": {"input": [raw_keyword, full_pinyin, first_letters], 
                                             "output": raw_keyword}}
            self.es.index(index=es_search_functions.getESItemIndexName(site_id), 
                          doc_type='keyword', body=result)

    def markKeywordsAsWhiteListed(self, site_id, keywords):
        #from recommender import es_client
        # also need to search and reindex the white listed keywords. use update api.
        # also update the keyword completion
        self.updateSuggestKeywordList(site_id, self.WHITE_LIST, keywords)
        self._indexKeywordsForCompletion(site_id, keywords)

    def markKeywordsAsBlackListed(self, site_id, keywords):
        self.updateSuggestKeywordList(site_id, self.BLACK_LIST, keywords)
        # TODO remove keywords for completion

keyword_list = KeywordList(es_search_functions.getESClient(), getMongoClient())
