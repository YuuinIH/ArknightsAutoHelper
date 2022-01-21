from penguin_stats import arkplanner
import requests
from datetime import datetime
import json
import os
import config
from automator import AddonBase
from ...stage_navigator import StageNavigator
from ...inventory import InventoryAddon

desc = f"""
{__file__}
==================================================================================================
长草时用的脚本, 检查库存中最少的蓝材料, 然后去 aog 上推荐的地图刷材料.
aog 地址: https://arkonegraph.herokuapp.com/

不想的刷的材料可以修改脚本中的 exclude_names.

cache_key 控制缓存的频率, 默认每周读取一次库存, 如果需要手动更新缓存, 
直接删除目录下的 aog_cache.json 和 inventory_items_cache.json 即可.

==================================================================================================
"""

# cache_key = '%Y-%m-%d'  # cache by day
cache_key = '%Y--%V'    # cache by week


aog_cache_file = os.path.join(config.cache_path, 'aog_cache.json')
inventory_cache_file = os.path.join(config.cache_path, 'inventory_items_cache.json')


def get_items_from_aog_api():
    resp = requests.get('https://arkonegraph.herokuapp.com/total/CN')
    return resp.json()


def update_aog_cache():
    data = {'aog': get_items_from_aog_api(), 'cacheTime': datetime.now().strftime(cache_key)}
    with open(aog_cache_file, 'w') as f:
        json.dump(data, f)
    return data


def load_aog_cache():
    if os.path.exists(aog_cache_file):
        with open(aog_cache_file, 'r') as f:
            data = json.load(f)
            if data['cacheTime'] == datetime.now().strftime(cache_key):
                return data
    return update_aog_cache()


def order_stage(item):
    if item['lowest_ap_stages']['normal'] and item['lowest_ap_stages']['event']:
        stage_type = 'lowest_ap_stages'
    elif item['balanced_stages']['normal'] and item['balanced_stages']['event']:
        stage_type = 'balanced_stages'
    else:
        stage_type = 'drop_rate_first_stages'
    event = item[stage_type]['event'][0]
    normal = item[stage_type]['normal'][0]
    return event if event['efficiency'] >= normal['efficiency'] else normal


class GrassAddOn(AddonBase):

    def on_attach(self) -> None:
        self.addon(StageNavigator).register_custom_stage('grass', self.run, ignore_count=True, title='一键长草', description='检查库存中最少的蓝材料, 然后去 aog 上推荐的地图刷材料')

    def run(self, argv):
        exclude_names = config.get('addons/grass_on_aog/exclude_names', ['固源岩组'])
        self.logger.info('不刷以下材料:', exclude_names)
        self.logger.info('加载库存信息...')
        aog_cache = load_aog_cache()
        my_items = self.load_inventory()
        all_items = arkplanner.get_all_items()

        l = []
        for item in all_items:
            if item['itemType'] in ['MATERIAL'] and item['name'] not in exclude_names and item['rarity'] == 2 \
                    and len(item['itemId']) > 4:
                l.append({'name': item['name'],
                          'itemId': item['itemId'],
                          'count': my_items.get(item['itemId'], 0),
                          'rarity': item['rarity']})
        l = sorted(l, key=lambda x: x['count'])
        print('require item: %s, owned: %s' % (l[0]['name'], l[0]['count']))
        aog_items = aog_cache['aog']
        t3_items = aog_items['tier']['t3']
        stage = ''
        for t3_item in t3_items:
            if t3_item['name'] == l[0]['name']:
                # print(t3_item)
                stage_info = order_stage(t3_item)
                stage = stage_info['code']
                self.logger.info('aog stage:', stage)
                break
        self.addon(StageNavigator).navigate_and_combat(stage, 1000)

    def load_inventory(self):
        if os.path.exists(inventory_cache_file):
            with open(inventory_cache_file, 'r') as f:
                data = json.load(f)
                if data['cacheTime'] == datetime.now().strftime(cache_key):
                    return data
        return self.update_inventory()

    def update_inventory(self):
        data = self.addon(InventoryAddon).get_inventory_items(True)
        data['cacheTime'] = datetime.now().strftime(cache_key)
        with open(inventory_cache_file, 'w') as f:
            json.dump(data, f)
        return data

__all__ = ['GrassAddOn']


if __name__ == '__main__':
    addon = GrassAddOn()
    addon.run()
