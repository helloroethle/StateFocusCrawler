import scrapy
from sqlalchemy.orm import sessionmaker
from ca_scraper.models import Legislators, db_connect, create_articles_table
from datetime import datetime
from sqlalchemy import and_
import time
from ca_scraper.items import PressRelease

class StateAssemblyRepublicanPressReleasesSpider(scrapy.Spider):
    name = 'state_assembly_republican_press_releases'
    def __init__(self):
      engine = db_connect()
      create_articles_table(engine)
      self.Session = sessionmaker(bind=engine)
    def start_requests(self):
      session = self.Session()
      for legie in session.query(Legislators).filter(and_(Legislators.party == 'Republican', Legislators.house == 'Assembly')):
        yield scrapy.Request(legie.official_site_url + '/press-releases', meta={'legie_id':legie.id})
      # test = 'https://ad40.asmrc.org/'
      # yield scrapy.Request(test + 'press-releases', callback=self.parse, meta={'legie_id':1})
    def parse(self, response):
      legie_id = response.meta.get('legie_id', 0)
      if response.status == 404 and not response.meta.get('existing_redirect', False):
        print('********* REDIRECT *********')
        print(response.request.url)
        yield scrapy.Request(response.request.url.replace('press-releases', 'press-release'), meta={existing_redirect:True, 'legie_id':legie_id})

      for press_release_year in response.css('div#block-system-main div.view-footer div.views-row a::attr(href)').extract():
        if press_release_year is not None:
          next_page = response.urljoin(press_release_year)
          print(next_page)
          yield scrapy.Request(next_page, callback=self.parse_feed_press_releases, meta={'legie_id':legie_id}, dont_filter = True)

    def parse_feed_press_releases(self, response):
      legie_id = response.meta.get('legie_id', 0)
      for press_release in response.css('div#block-system-main>div.view-press-releases>div.view-content div.views-row'):
        link = response.urljoin(press_release.css('div.views-field-title a::attr(href)').extract_first())
        print(link)
        yield scrapy.Request(link, callback=self.parse_press_release, meta={'legie_id':legie_id})

      next_page = response.css('li.pager-next a::attr(href)').extract_first()
      if next_page is not None:
          next_page = response.urljoin(next_page)
          yield scrapy.Request(next_page, callback=self.parse_feed_press_releases, meta={'legie_id':legie_id})

    def parse_press_release(self, response):
      legie_id = response.meta.get('legie_id', 0)
      title = response.css('h1.carousel-heading-title::text').extract_first()
      content = ' '.join([x.strip() for x in response.css('div.field-name-body *::text').extract() if x])
      timestamp = response.css('span.date-display-single::attr(content)').extract_first()
      timestamp_extracted = time.strptime(timestamp[:19], "%Y-%m-%dT%H:%M:%S")
      published = datetime(*timestamp_extracted[:6])
      yield PressRelease(
        title = title,
        url = response.request.url,
        published = published,
        content = content,
        legislator = str(legie_id)
      )