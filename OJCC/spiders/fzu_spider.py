from scrapy.spiders import Spider
from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor as link
from scrapy.http import Request, FormRequest
from scrapy.selector import Selector
from OJCC.items import ProblemItem, SolutionItem
from base64 import b64decode
import time

LANGUAGE = {
        'g++': '0',
        'gcc': '1',
        'pascal': '2',
        'java': '3',
        'c++': '4',
        'c': '5'
    }

class FzuInitSpider(CrawlSpider):
    name = 'fzu_init'
    allowed_domains = ['acm.fzu.edu.cn']

    start_urls = [
        'http://acm.fzu.edu.cn/list.php'
    ]

    rules = [
        Rule(
            link(
                allow=('list.php\?vol=[0-9]+'),
                unique=True
            )),
        Rule(
            link(
                allow=('problem.php\?pid=[0-9]+')
            ), callback='problem_item')
    ]

    def problem_item(self, response):
        sel = Selector(response)

        item = ProblemItem()
        item['origin_oj'] = 'fzu'
        item['problem_id'] = response.url[-4:]
        item['problem_url'] = response.url
        item['title'] = sel.xpath(
            '//div[contains(@class, "problem_title")]/b/text()').extract()[0]
        item['description'] = sel.css('.pro_desc').extract()[0]

        try:
            item['input'] = sel.css('.pro_desc').extract()[1]
        except:
            item['input'] = []

        try:
            item['output'] = sel.css('.pro_desc').extract()[2]
        except:
            item['output'] = []

        item['time_limit'] = sel.css('.problem_desc').re('T[\S*\s]*c')[0]
        item['memory_limit'] = sel.css('.problem_desc').re('M[\S*\s]*B')[0]
        item['sample_input'] = sel.css('.data').extract()[0]
        item['sample_output'] = sel.css('.data').extract()[1]
        return item

class FzuProblemSpider(Spider):
    name = 'fzu_problem'
    allowed_domains = ['acm.fzu.edu.cn']

    def __init__(self, problem_id='1000', *args, **kwargs):
        self.problem_id = problem_id
        super(FzuProblemSpider, self).__init__(*args, **kwargs)
        self.start_urls = [
            'http://acm.fzu.edu.cn/problem.php?pid=%s' % problem_id
        ]

    def parse(self, response):
        sel = Selector(response)

        item = ProblemItem()
        item['origin_oj'] = 'fzu'
        item['problem_id'] = self.problem_id
        item['problem_url'] = response.url
        item['title'] = sel.xpath(
            '//div[contains(@class, "problem_title")]/b/text()').extract()[0]
        item['description'] = sel.css('.pro_desc').extract()[0]
        try:
            item['input'] = sel.css('.pro_desc').extract()[1]
        except:
            item['input'] = []
        try:
            item['output'] = sel.css('.pro_desc').extract()[2]
        except:
            item['output'] = []
        item['time_limit'] = sel.css('.problem_desc').re('T[\S*\s]*c')[0]
        item['memory_limit'] = sel.css('.problem_desc').re('M[\S*\s]*B')[0]
        item['sample_input'] = sel.css('.data').extract()[0]
        item['sample_output'] = sel.css('.data').extract()[1]
        return item

class FzuSubmitSpider(CrawlSpider):
    name = 'fzu_submit'
    allowed_domains = ['acm.fzu.edu.cn']
    login_url = 'http://acm.fzu.edu.cn/login.php?act=1&dir='
    submit_url = 'http://acm.fzu.edu.cn/submit.php?act=5'
    source = \
        'I2luY2x1ZGUgPHN0ZGlvLmg+CgppbnQgbWFpbigpCnsKICAgIGludCBhLGI7CiAgICBzY2FuZigiJWQgJWQiLCZhLCAmYik7CiAgICBwcmludGYoIiVkXG4iLGErYik7CiAgICByZXR1cm4gMDsKfQ=='

    start_urls = [
            "http://acm.fzu.edu.cn/log.php"
    ]

    rules = [
        Rule(
            link(
                allow=('log.php\?&page=[0-9]+'),
                deny=('log.php\?&page=1$')
            ), follow=True, callback='parse_start_url')
    ]

    username = 'sdutacm1'
    password = 'sdutacm'

    is_judged = False

    def __init__(self,
            problem_id='1000',
            language='g++',
            source=None, *args, **kwargs):
        super(FzuSubmitSpider, self).__init__(*args, **kwargs)

        self.problem_id = problem_id
        self.language = LANGUAGE.get(language, '0')
        if source is not None:
            self.source = source

    def start_requests(self):
        return [FormRequest(self.login_url,
                formdata = {
                        'uname': self.username,
                        'upassword': self.password,
                        'submit': 'Submit',
                },
                callback = self.after_login,
                dont_filter = True
        )]

    def after_login(self, response):
        self.login_time = time.mktime(time.strptime(\
                response.headers['Date'], \
                '%a, %d %b %Y %H:%M:%S %Z')) + (8 * 60 * 60)
        time.sleep(1)
        return [FormRequest(self.submit_url,
                formdata = {
                        'pid': self.problem_id,
                        'lang': self.language,
                        'code': b64decode(self.source),
                        'submit': 'Submit',
                },
                callback = self.after_submit,
                dont_filter = True
        )]

    def after_submit(self, response):
        time.sleep(10)
        for url in self.start_urls :
            yield self.make_requests_from_url(url)

    def parse_start_url(self, response):
        if self.is_judged:
            self._rules = []

        sel = Selector(response)

        item = SolutionItem()
        for tr in sel.xpath('//table/tr')[1:]:
            user = tr.xpath('.//td/a/text()').extract()[-1]
            _submit_time = tr.xpath('.//td/text()').extract()[1]
            submit_time = time.mktime(\
                    time.strptime(_submit_time, '%Y-%m-%d %H:%M:%S'))
            if submit_time > self.login_time and \
                    user == self.username:
                item['origin_oj'] = 'hdu'
                item['problem_id'] = self.problem_id
                item['language'] = self.language
                item['submit_time'] = _submit_time
                item['run_id'] = tr.xpath('.//td/text()').extract()[0]

                try:
                    item['memory'] = \
                        tr.xpath('.//td')[5].xpath('./text()').extract()[0]
                    item['time'] = \
                        tr.xpath('.//td')[6].xpath('./text()').extract()[0]
                except:
                    item['memory'] = []
                    item['time'] = []
                item['code_length'] = tr.xpath('.//td/text()').extract()[-1]
                item['result'] = tr.xpath('.//td/font/text()').extract()[0]
                self.is_judged = True
                return item
