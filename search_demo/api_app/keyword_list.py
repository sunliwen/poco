from api_app import es_search_functions
from common.mongo_client import getMongoClient


class KeywordList:
    WHITE_LIST = "W"
    BLACK_LIST = "B"
    UNIDENTIFIED_LIST = "U"

    def __init__(self, es, mongo_client):
        self.es = es
        self.mongo_client = mongo_client

    def getKeywordStatus(self, site_id, keyword):
        keyword_status = self.mongo_client.getSuggestKeywordStatus(site_id, keyword)
        return keyword_status

    # return accepted_keywords and update unidentified keywords to db.
    def processKeywords(self, site_id, keywords):
        accepted_keywords, to_be_in_unidentified_keywords = [], []
        for keyword in keywords:
            keyword_status = self.mongo_client.getSuggestKeywordStatus(site_id, keyword)
            if keyword_status == self.WHITE_LIST:
                accepted_keywords.append(keyword)
            elif keyword_status == None:
                to_be_in_unidentified_keywords.append(keyword)
        self._updateUnidentifiedKeywords(site_id, to_be_in_unidentified_keywords)
        return accepted_keywords

    def _updateUnidentifiedKeywords(self, site_id, to_be_in_unidentified_keywords):
        self.mongo_client.updateSuggestKeywordList(site_id, self.UNIDENTIFIED_LIST, 
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
        self.mongo_client.updateSuggestKeywordList(site_id, self.WHITE_LIST, keywords)
        self._indexKeywordsForCompletion(site_id, keywords)

    def markKeywordsAsBlackListed(self, site_id, keywords):
        self.mongo_client.updateSuggestKeywordList(site_id, self.BLACK_LIST, keywords)
        # TODO reindex items
        # TODO remove keywords for completion

keyword_list = KeywordList(es_search_functions.getESClient(), getMongoClient())
