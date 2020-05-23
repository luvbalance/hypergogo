import discord
import datetime
import time
from discord.ext import tasks
from discord.ext import commands
import os
import traceback
import re       #正規表現
import random   #乱数
import redis    #DB(redis)
import pickle   #オブジェクトのシリアライズ/デシリアライズ
import json     #json(クラス値をredisでjson方式で保存/復元するために使用)

from PIL import Image, ImageDraw, ImageFilter, ImageFont
import io

#redis接続オブジェクト取得
def connect():
    #return redis.from_url(url="redis://localhost", decode_responses=True)
    return redis.from_url(url=os.environ.get('REDIS_URL'), decode_responses=True)

#実行する環境の環境変数に'DISCORD_BOT_TOKEN_HYPERGOGO'を登録しておけば、
#ローカルPC実行、Heloku実行どちらでも対応可能です。
token = os.environ['DISCORD_BOT_TOKEN_HYPERGOGO']

#完了メッセージ定義
compmes =['{0}機修理できました'
        ,'{0}機修理できたような気がする'
        ,'{0}機、これで治ったかしら…'
        ,'{0}機修理できました！'
        ,'{0}機修理完了です'
        ,'{0}機修理完了！'
        ,'{0}機、間に合ったかしら'
        ,'{0}機修理したよー'
        ,'{0}機準備しといたぞ'
        ,'{0}機、いつでも行けるぞ'
        ,'{0}機だ…さっさと行ってこい！'
        ,'{0}機修理できましたわ'
        ,'{0}機…使って'
        ,'{0}機…使えばいいと思うよ'
        ,'{0}機、大事に使えよ'
        ,'{0}機、大切にしてね'
        ,'{0}機…2度と壊すなよ'
        ,'{0}機…死ぬなよ'
        ,'{0}機…絶対帰ってきてね'
        ,'この{0}機、無駄にするなよ'
        ,'{0}機治しておいてやったぞ'
        ,'約束の{0}機だ…'
        ,'{0}機…代金はあとでいい…'
        ,'{0}機…いや、なんでもない'
        ,'{0}機…あとで奢れよ'
        ,'ほら、{0}機だ'
        ,'{0}機だ、持ってけ'
        ]

#完了メッセージの取得
def getcompmes(compcount):
    base = random.randint(0, 4)
    if base == 0:
        # 1/5の確率でレアメッセージ出現
        mes = compmes[random.randint(1, len(compmes)-1)]
        return mes.format(str(compcount))
    else:
        # 9/10の確率で通常メッセージ
        return compmes[0].format(str(compcount))

#ヘルプ
def helpstr():
    retstr = '**使い方**\n'
    retstr += '\t/gogohelp\tヘルプ表示\n'
    retstr += '\t/init\t待機状況初期化(テキスト表示)\n'
    retstr += '\t/vinit\t待機状況初期化(描画表示)\n'
    retstr += '\t/stat\t待機状況表示(テキスト表示)\n'
    retstr += '\t/vstat\t待機状況表示(描画表示)\n'
    retstr += '\t/xyz (rw1) (rw2) (rw3)\t待機状況登録\n'
    retstr += '\t\tx...待機数(0～3)\n'
    retstr += '\t\ty...無料回復数(0～9)\n'
    retstr += '\t\tz...修理数(0～3)\n'
    retstr += '\t\t※修理数は待機数に応じて補正あり\n'
    retstr += '\t\t(rw1)...修理時間(1台目)(省略可能)\n'
    retstr += '\t\t(rw2)...修理時間(2台目)(省略可能)\n'
    retstr += '\t\t(rw3)...修理時間(3台目)(省略可能)\n'
    retstr += '\t\t※修理時間の単位は分\n'
    retstr += '\t\t※修理時間指定数に対して\n'
    retstr += '\t\t　修理時間を少なく指定した場合は\n'
    retstr += '\t\t　修理時間を\n'
    retstr += '\t\t　全台に適用します\n'
    retstr += '\t\t\n'
    retstr += '\t\tex.\n'
    retstr += '\t\t/320\n'
    retstr += '\t\t/102 120 110\n'
    return retstr

#指定datetimeにadd分を足す
def getWT(ct, add):
    return ct + datetime.timedelta(minutes=add)

#ミリ秒を０とした現在日時の取得
def getNowTimeNoMill():
    now_time = datetime.datetime.now().replace(second=0).replace(microsecond=0)
    return now_time

#指定datetimeのフォーマット文字列%H:%Mを返す
def GetRWTimeStr(rw):
    if(rw==''):
        return ""
    return rw.strftime("%H:%M")

#半角数値文字列をアイコン文字列に置き換えます
def NumIcomStr(numstr):
    retstr = ''
    numstrlist = list(numstr)
    for value in numstrlist:
        retstr+=NumIcon(value)
    return retstr

#半角数字1文字をアイコンに置き換えます
def NumIcon(value):
    ret = ''
    if value=='0':
        ret = ':zero:'
    elif value=='1':
        ret = ':one:'
    elif value=='2':
        ret = ':two:'
    elif value=='3':
        ret = ':three:'
    elif value=='4':
        ret = ':four:'
    elif value=='5':
        ret = ':five:'
    elif value=='6':
        ret = ':six:'
    elif value=='7':
        ret = ':seven:'
    elif value=='8':
        ret = ':eight:'
    elif value=='9':
        ret = ':nine:'

    return ret

#サーバー毎の状態クラス
class ServerInfo:
    def __init__(self, statinfos, channelid, isdraw):
        self.statinfos = statinfos
        self.channelid = channelid
        self.isdraw = isdraw

#メンバー一人分の状態管理クラス
class Statinfo:
    def __init__(self, ct, userid, channelid, wait, recover, repair, rw1, rw2, rw3):
        self.ct = ct            #登録/更新日 (datetime)
        self.Userid = userid        #メンバーを示すDiscordのユーザー情報
        self.Channelid = channelid  #メンバーが状態登録を送信したDiscordのチャンネル情報
        self.wait = wait        #待機数 (int)
        self.recover = recover  #回復数 (int)
        self.repair = repair    #入院数 (int)
        self.rw1 = rw1          #修理完了時間1 (datetime or None)
        self.rw2 = rw2          #修理完了時間2 (datetime or None)
        self.rw3 = rw3          #修理完了時間3 (datetime or None)
        return
    # 
    def stat(self):
        return str(self.wait) + str(self.recover) +str(self.repair)
    def updaterw3(self, now_time):
        if not self.rw3 is None:
            if(now_time >= self.rw3):
                self.rw3 = None
                if self.repair >0:
                    self.repair -= 1
                    self.wait += 1
                return True
        return False

    def updaterw2(self, now_time):
        if not self.rw2 is None:
            if(now_time >= self.rw2):
                self.rw2 = None
                if self.repair >0:
                    self.repair -= 1
                    self.wait += 1
                if not self.rw3 is None:
                    self.rw2 = self.rw3
                    self.rw3=None
                return True
        return False

    def updaterw1(self, now_time):
        if not self.rw1 is None:
            if(now_time >= self.rw1):
                self.rw1 = None
                if self.repair >0:
                    self.repair -= 1
                    self.wait += 1
                if not self.rw2 is None:
                    self.rw1 = self.rw2
                    self.rw2 = None
                if not self.rw3 is None:
                    if self.rw1 is None:
                        self.rw1 = self.rw3
                        self.rw3 = None
                    elif self.rw2 is None:
                        self.rw2 = self.rw3
                        self.rw3 = None
                return True
        return False
    def showstat(self):
        User = client.get_user(self.Userid)
        retstr = self.ct.strftime("%H:%M")+' '+User.display_name
        retsubstr = ''
        if not self.rw1 is None:
            retsubstr += GetRWTimeStr(self.rw1)

        if not self.rw2 is None:
            if(len(retsubstr)>0):
                retsubstr += ','
            retsubstr += GetRWTimeStr(self.rw2)

        if not self.rw3 is None:
            if(len(retsubstr)>0):
                retsubstr += ','
            retsubstr += GetRWTimeStr(self.rw3)

        retstr += '\n\t'
        retstr += NumIcon(str(self.wait))
        retstr += NumIcon(str(self.recover))
        retstr += NumIcon(str(self.repair))
        if retsubstr !='':
            retstr += ' :hospital:('+retsubstr+')'
        else:
            retstr += ' :hospital:(-)'
        return retstr
    def drwastat(self, draw, index):
        yy = index * 18
        fontnum = ImageFont.truetype('./fonts/GenShinGothic-Regular.ttf', 12)
        
        num_h = 1
        xx = 2
        fontjp = ImageFont.truetype('./fonts/GenShinGothic-Regular.ttf', 12)
        #draw.rectangle((0, 0, 36, 16), fill=(216, 191, 216), outline=(255, 255, 255))
        draw.rectangle((1, 1+yy, 41, 16+yy), fill=(63, 72, 204), outline=(112, 146, 190))
        draw.multiline_text((4+xx, num_h+yy), self.ct.strftime("%H:%M"), fill=(255, 255, 255), font=fontnum)
        draw.rectangle((41, 1+yy, 54, 16+yy), fill=(63, 72, 204), outline=(112, 146, 190))
        draw.multiline_text((44-1+xx, num_h+yy), str(self.wait), fill=(255, 255, 255), font=fontnum)
        draw.rectangle((54, 1+yy, 67, 16+yy), fill=(63, 72, 204), outline=(112, 146, 190))
        draw.multiline_text((57-1+xx, num_h+yy), str(self.recover), fill=(255, 255, 255), font=fontnum)
        draw.rectangle((67, 1+yy, 80, 16+yy), fill=(63, 72, 204), outline=(112, 146, 190))
        draw.multiline_text((70-1+xx, num_h+yy), str(self.repair), fill=(255, 255, 255), font=fontnum)
        draw.multiline_text((82, 1+yy), self.User.display_name, fill=(255, 255, 255), font=fontjp)

        #fill=(63, 72, 204)
        #fill=(139, 0, 139)
        if not self.rw1 is None:
            draw.rectangle((177, 1+yy, 217, 16+yy), fill=(139, 0, 139), outline=(112, 146, 190))
            draw.multiline_text((180+xx, num_h+yy), GetRWTimeStr(self.rw1), fill=(255, 255, 255), font=fontnum)

        if not self.rw2 is None:
            draw.rectangle((217, 1+yy, 257, 16+yy), fill=(139, 0, 139), outline=(112, 146, 190))
            draw.multiline_text((220+xx, num_h+yy), GetRWTimeStr(self.rw2), fill=(255, 255, 255), font=fontnum)

        if not self.rw3 is None:
            draw.rectangle((257, 1+yy, 297, 16+yy), fill=(139, 0, 139), outline=(112, 146, 190))
            draw.multiline_text((260+xx, num_h+yy), GetRWTimeStr(self.rw3), fill=(255, 255, 255), font=fontnum)

        return

class GogoJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Statinfo):
            jsonstr = '{'
            jsonstr += '\'ct\':' + '\''+ o.ct.isoformat() + '\''
            jsonstr += ','
            jsonstr += '\'User\':' + str(o.User.id)
            jsonstr += ','
            jsonstr += '\'Channel\':' + str(o.Channelid)
            jsonstr += ','
            jsonstr += '\'wait\':' + str(o.wait)
            jsonstr += ','
            jsonstr += '\'recover\':' + str(o.recover)
            jsonstr += ','
            jsonstr += '\'repair\':' + str(o.repair)
            jsonstr += ','
            jsonstr += '\'rw1\':' + '\''+ o.rw1.isoformat() + '\''
            jsonstr += ','
            jsonstr += '\'rw2\':' + '\''+ o.rw2.isoformat() + '\''
            jsonstr += ','
            jsonstr += '\'rw3\':' + '\''+ o.rw3.isoformat() + '\''
            jsonstr += '}'
            return jsonstr
        return super(GogoJSONEncoder, self).default(o)
        
#これはbot frameworkを使った書き方(discordpy-startupのサンプルコードのまま)
#bot = commands.Bot(command_prefix='/')
#@bot.event
#async def on_command_error(ctx, error):
#    orig_error = getattr(error, "original", error)
#    error_msg = ''.join(traceback.TracebackException.from_exception(orig_error).format())
#    await ctx.send(error_msg)


#@bot.command()
#async def ping(ctx):
#    await ctx.send('pong')

#@bot.command()
#async def ping2(ctx):
#    await ctx.send('pong2')

#bot.run(token)

# 接続に必要なdiscord.Clientオブジェクトを生成
client = discord.Client()

# 起動時に動作する処理
@client.event
async def on_ready():
    # 起動したらターミナルにログイン通知が表示される
    print('gogocats logged in')

#============================================================
# ループ処理のコア実装
# 30秒に一回ループ
#============================================================
@tasks.loop(seconds=1)
async def loop():
    now_time = getNowTimeNoMill()
    print(datetime.datetime.now().strftime('%H:%M:%S') +' ' +now_time.strftime('%H:%M:%S'))
    
    #メンバー修理時間の減算処理
    for server_info in server_infos.values():
        stat_infos = server_info.statinfos
        for stat_info in stat_infos.values():
            
            compcount = 0
            if stat_info.updaterw3(now_time):
                compcount+=1
            if stat_info.updaterw2(now_time):
                compcount+=1
            if stat_info.updaterw1(now_time):
                compcount+=1
            if compcount>0:
                stat_info.ct = getNowTimeNoMill()
                #sendstr = stat_info.User.display_name+' '+str(compcount)+'台修理できました！\n'
                #sendstr = f'{stat_info.User.mention}'+' '+str(compcount)+'台修理できました！\n'
                sendstr = f'{stat_info.User.mention}'+' '+getcompmes(compcount)+'\n'
                sendstr+= stat_info.showstat()
                channel = client.get_channel(stat_info.Channelid)
                await channel.send(sendstr)

#============================================================
#ループ処理実行
#メモ：bot接続前にループ開始する
#============================================================
loop.start()

#サーバーID毎のメンバー状態ハッシュリスト管理用
server_infos = {}

#サーバーID毎の初期化依頼時のチャンネルハッシュリスト管理用(※退院通知に使用する)
server_infos_channel = {}

#============================================================
# メッセージ受信時に動作する処理
#============================================================
@client.event
async def on_message(message):
    # メッセージ送信者がBotだった場合は無視する
    # メモ：こうしておかないと、Botへ応答送信したメッセージを再度受信することになる
    if message.author.bot:
        return

    # 受信メッセージを解析して配列にしておく
    # 区切り文字はコマンドの区切り文字
    # ex."/test 1 2 3"　なら"['/test','1','2','3']の配列が取得できる
    params = message.content.split(" ")
    paramslen = len(params)
    command = params[0]
    #
    print('■受信メッセージ', message.content)
    print('  SPで区切った要素', params, '要素数', paramslen)
    print('  送信者', message.author.name, message.author.id)
    print('  discordサーバー名/ID', message.guild.name, message.guild.id)
    print('  チャンネル名/ID', message.channel.name, message.channel.id)

    # 1番目の要素(=コマンド名)によって分岐する
    result = re.match(r'(/)([0-9]{3})', command)
    if result:
        #============================================================
        #状態登録
        #params[0] /abc
        # a...残機数
        # b...回復数
        # c...入院数
        #params[1] 退院時間1(省略可)
        #params[2] 退院時間2(省略可)
        #params[3] 退院時間3(省略可)
        #============================================================
        #パラメータチェック
        if(paramslen<1):
            await message.channel.send('パラメータが足りません。\n(/helpで使い方を表示)')
            return
        statstr = result.group(2)
        wait = int(statstr[0])
        if(wait > 3):
            wait = 3
        recover = int(statstr[1])
        repair = int(statstr[2])
        if(repair > 3):
            repair = 3
        if(wait + repair > 3):
            repair = 3 - wait

        rw1 = None
        rw2 = None
        rw3 = None
        ct = getNowTimeNoMill()
        if(repair > 0):
            if(paramslen > 1 and str.isnumeric(params[1]) and int(params[1])>0):
                rw1 = getWT(ct, int(params[1]))
        if(repair > 1):
            if(paramslen > 2 and str.isnumeric(params[2]) and int(params[2])>0):
                rw2 = getWT(ct, int(params[2]))
            else:
                rw2 = rw1
        if(repair > 2):
            if(paramslen > 3 and str.isnumeric(params[1]) and int(params[3])>0):
                rw3 = getWT(ct, int(params[3]))
            elif rw2!='':
                rw3 = rw2
            else:
                rw3 = rw1

        #サーバーID文字列の取得(メンバー状態ハッシュリストを取り出すためのキーとして使用)
        guild_key = str(message.guild.id)
        #送信者ID文字列の取得(メンバー状態ハッシュリストのキーとして使用)
        author_key = str(message.author.id)

        
        #サーバーIDに対応するメンバー状態ハッシュリストが生成されていない場合は生成する
        if not guild_key in server_infos:
            #server_infos[guild_key] = {}
            server_infos[guild_key] = ServerInfo({}, message.channel.id, False)

        #サーバーIDに対応するメンバー状態ハッシュリストの取得
        #stat_infos = server_infos[guild_key]
        server_info = server_infos[guild_key]
        stat_infos = server_info.statinfos

        #送信者メンバーが状態ハッシュリストに存在しない場合は
        if not author_key in stat_infos:
            #送信者メンバー状態をハッシュリストに追加
            stat_infos[author_key] = Statinfo(ct, message.author.id, message.channel.id, wait, recover, repair, rw1, rw2, rw3)
        #送信者メンバー状態の更新
        stat_infos[author_key].ct = getNowTimeNoMill()
        stat_infos[author_key].Channelid = message.channel.id
        stat_infos[author_key].wait = wait
        stat_infos[author_key].recover = recover
        stat_infos[author_key].repair = repair
        stat_infos[author_key].rw1 = rw1
        stat_infos[author_key].rw2 = rw2
        stat_infos[author_key].rw3 = rw3

        #登録完了
        if(server_info.isdraw):
            im = Image.new('RGB', (300, 18), (80, 80, 80))
            draw = ImageDraw.Draw(im)

            stat_infos[author_key].drwastat(draw, 0)

            output = io.BytesIO()
            #with BytesIO() as image_binary:
            with output as image_binary:
                im.save(image_binary, 'PNG')
                image_binary.seek(0)
                await message.channel.send(file=discord.File(fp=image_binary, filename='image.png'))
            im.close()
        else:
            retstr = stat_infos[author_key].showstat()
            await message.channel.send(retstr)
        return
    elif command == '/conf':
        #============================================================
        # 動作設定のみ更新
        #============================================================
        #サーバーID文字列の取得(メンバー状態ハッシュリストを取り出すためのキーとして使用)
        guild_key = str(message.guild.id)
        
        isdraw = False
        if(paramslen>0):
            if(params[1]=='v'):
                isdraw = True
            elif(params[1]=='t'):
                isdraw = False

        server_info = None
        if not guild_key in server_infos:
            server_info = ServerInfo({}, message.channel.id, False)
            server_infos[guild_key] = server_info
        else:
            server_info = server_infos[guild_key]

        server_info.isdraw = isdraw
        await message.channel.send('**動作設定を更新しました**')
        return

    elif command == '/init' or command == '/vinit':
        #============================================================
        #状態初期化
        #============================================================
        #サーバーID文字列の取得(メンバー状態ハッシュリストを取り出すためのキーとして使用)
        guild_key = str(message.guild.id)
        #サーバーIDに対応するメンバー状態ハッシュリストを初期化
        #server_infos[guild_key] = {}
        isdraw = (command == '/vinit')
        server_infos[guild_key] = ServerInfo({}, message.channel.id,isdraw)
        
        #stat_infos = server_infos[guild_key]
        #for User in message.channel.Users:
            #stat_infos[author_key] = Statinfo(User, 3, 2, 0)

        await message.channel.send('**待機状況を初期化しました**')
        return

    elif command == '/stat' or command == '/vstat':
        #============================================================
        #状態一覧表示
        #============================================================

        guild_key = str(message.guild.id)
        server_info = None
        if not guild_key in server_infos:
            server_info = ServerInfo({}, message.channel.id, False)
            server_infos[guild_key] = server_info
        else:
            server_info = server_infos[guild_key]        
        stat_infos = server_info.statinfos

        #集計
        c_player = 0    #メンバー数
        c_wait = 0      #総待機数
        c_repair = 0    #総修理数
        c_all = 0       #総機体数

        #メンバー状態情報を全て参照して集計
        for stat_info in stat_infos.values():
            c_player +=1
            c_wait += stat_info.wait
            c_repair += stat_info.repair
        #総機体数 = メンバー数 x 3
        c_all = c_player * 3
        #総出撃数 = 総機体数 - 総待機数 - 総修理数
        c_go = c_all - c_wait - c_repair

        #送信文字列の生成
        #1行目
        row1 = '**待機状況**(登録メンバー数:'+str(c_player)+')'
        retstr = row1+'\n'
        #2行目
        row2 = '待機数/機体数:'+ str(c_wait)+ '/' + str(c_all)
        if(c_player>0):
            row2 +='('+str(c_wait*100//c_all)+'%)'
        retstr += row2+'\n'
        #3行目
        row3 = '出撃数/機体数:'+ str(c_go)+ '/' + str(c_all)
        if(c_player>0):
            row3 +='('+str(c_go*100//c_all)+'%)'
        retstr+= row3 + '\n'
        #retstr += '\t\t\t:free::heart_decoration::ambulance:\n'
        #4行目～ 各メンバー状態
        #stat_infos_sorted = sorted(stat_infos, key=lambda x:x['ct'])

        if(command=='/vstat' or server_info.isdraw):
            #----------------------------------------
            #描画表示
            #----------------------------------------
            #(105, 105, 105)
            im = Image.new('RGB', (300, 18 * 3 + 18 * c_player), (80, 80, 80))
            #im = Image.new('RGB', (300, 18), (128, 128, 128))
            #im = Image.open('./images/bg.png')
            draw = ImageDraw.Draw(im)

            fontjp = ImageFont.truetype('./fonts/GenShinGothic-Regular.ttf', 12)
            num_y=2
            draw.multiline_text((1, 1+18*0), row1, fill=(255, 255, 255), font=fontjp)
            draw.multiline_text((1, 1+18*1), row2, fill=(255, 255, 255), font=fontjp)
            draw.multiline_text((1, 1+18*2), row3, fill=(255, 255, 255), font=fontjp)

            index = 3
            for stat_info in stat_infos.values():
                stat_info.drwastat(draw, index)
                index+=1

            output = io.BytesIO()
            #with BytesIO() as image_binary:
            with output as image_binary:
                im.save(image_binary, 'PNG')
                image_binary.seek(0)
                await message.channel.send(file=discord.File(fp=image_binary, filename='image.png'))
            im.close()
        else:
            #----------------------------------------
            #テキスト表示
            #----------------------------------------
            for stat_info in stat_infos.values():
                retstr += stat_info.showstat()+'\n'

            await message.channel.send(retstr)
        return

    elif command == '/chlist':
        #============================================================
        #chlist
        #============================================================
        # コマンド'/test'の実装
        #テストコード：接続先サーバーの全テキストチャンネルの抽出
        text_channel_list = []
        for channel in message.guild.text_channels:
            text_channel_list.append(channel)
        #これだと全サーバー分の抽出
        #for guild in client.guilds:
        #    for channel in guild.text_channels:
        #        text_channel_list.append(channel)
        retstr = '**テキストチャンネル一覧**\n'
        for text_channel in text_channel_list:
            retstr += '・['+str(text_channel.id)+']'+text_channel.name+'\n'
        await message.channel.send(retstr)
        print(retstr)

        return


    elif command ==  '/settest':
        conn = connect()
        result = conn.set('test', '123')
        print(result)
        return 
    elif command ==  '/gettest':
        conn = connect()
        res2 = conn.get('test')
        print(res2)
        return 
    elif command ==  '/enc':
        stat = Statinfo(datetime.datetime.now(), message.author.id, message.channel.id, 1, 2, 3, datetime.datetime.now(), datetime.datetime.now(), datetime.datetime.now())
        ret = json.dumps(stat, cls=GogoJSONEncoder)
        print(ret)
        return 


    elif command ==  '/encp':
        stat = Statinfo(datetime.datetime.now(), message.author.id, message.channel.id, 1, 2, 3, datetime.datetime.now(), datetime.datetime.now(), datetime.datetime.now())
        #ret = json.dumps(stat, cls=GogoJSONEncoder)
        ret = pickle.dumps(stat)
        print(ret)
        stat2 = pickle.loads(ret)
        print(stat2)
        return

    elif command ==  '/encp2':
        stat = Statinfo(datetime.datetime.now(), message.author.id, message.channel.id, 1, 2, 3, datetime.datetime.now(), datetime.datetime.now(), datetime.datetime.now())
        server = ServerInfo({},message.channel.id,False)
        stat_infos = server.statinfos
        stat_infos['test'] = stat
        #ret = json.dumps(stat, cls=GogoJSONEncoder)
        ret = pickle.dumps(server)
        print(ret)
        server = pickle.loads(ret)
        print(server)
        return

    elif command == '/gogohelp':
        await message.channel.send(helpstr())
        return

#============================================================
#clientの接続
#これで実行開始します
#成功すると、discord側のbotメンバーがアクティブになります
#============================================================
client.run(token)

