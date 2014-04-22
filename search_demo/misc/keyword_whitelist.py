# encoding=utf8
import os.path

# http://pinyin.sogou.com/dict/cell.php?id=6925
list1 = """摇摆椅 康康电动椅 好孩子 日康浴盆
新安怡 强生 菲力洁 旭贝儿
安满 奶粉 自行车 扭扭车
摇摆车 摇篮 红蜻蜓 爱儿健
婴之坊 英氏 服装 毛巾
袜子 帽子 毯子 毛被
蚕丝被 孕妇 宜栖 胸罩
快乐屋 德莱茜 长裤 防辐射
用品 奶嘴 安抚奶嘴 绵羊油
食品 惠氏 美赞臣 贝因美
雅培 雅士利 多美滋 蓓宝
枕头 足球 篮球 羊角球
不倒翁 宝高 制高 画架板
电子琴 木马 小猫钓鱼 小熊穿衣
退货 残次 有异常
人民店 道二店 相城店 绿宝店
吴中店 蠡口店 胥店 石路店
总仓 残次退总仓 仓库"""

# http://pinyin.sogou.com/dict/cell.php?id=33615
list2 = """爱迪生 爱可丁 爱馨多 澳美多
澳优 巴比纳 百利乐 百维滋
宝素力 贝贝安琪 贝多分 贝因美
贝智康 倍爱 聪尔壮 多美滋
飞鹤 关山 光明 荷兰朵
合生元 亨氏 慧牛 惠氏
江心 金哥贝 可尼可 莱那珂
乐氏 林贝儿 龙丹 美可高特
美素 美赞臣 美智宝 蒙牛
明一 明治 南山 牛栏
纽利兹 欧贝儿 欧来 普乐娃
雀巢 三鹿 三元 森永
善臣 圣元 施恩 太子乐
娃哈哈 完达山 维维 喜安智
新怡 熊猫 旭贝尔 雅培
雅士利 羊百利 摇篮 伊利
永卓 御宝 纽莱可 牛奶客"""

def extract_word_list(str):
    return set([word.strip() for word in str.split() if word.strip()])

def load_sorted_unique_words():
    file_path = os.path.join(os.path.split(__file__)[0], "sorted_unique_words1.txt")
    f = open(file_path, "r")
    words = []
    for line in f.readlines():
        word = line.split()[0]
        words.append(word)
    return set(words)

KEYWORD_WHITELIST = extract_word_list(list1) | extract_word_list(list2) | load_sorted_unique_words()

if __name__ == "__main__":
    print u"伊威" in KEYWORD_WHITELIST
