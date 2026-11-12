"""Public brand assets. No procurement content is used in previews."""
from functools import lru_cache
import io

@lru_cache(maxsize=2)
def brand_png(preview=False):
    from PIL import Image, ImageDraw, ImageFont
    red='#d62236'; ink='#171717'
    if preview:
        im=Image.new('RGB',(1200,630),'#ffffff')
    else:
        im=Image.new('RGB',(96,96),'#ffffff')
    d=ImageDraw.Draw(im)
    def mark(x,y,s):
        def xy(a,b):return (round(x+a*s),round(y+b*s))
        # Same octopus identity as the navigation mark, with a rounded body.
        d.line([xy(14,25),xy(9,32),xy(9,38),xy(13,39),xy(17,34)],fill=red,width=max(2,round(s*4)),joint='curve')
        d.line([xy(34,25),xy(39,32),xy(39,38),xy(35,39),xy(31,34)],fill=red,width=max(2,round(s*4)),joint='curve')
        d.rounded_rectangle([xy(13,7),xy(35,40)],radius=round(11*s),fill=red)
        for a in (20,28):
            d.ellipse([xy(a-1.9,22),xy(a+1.9,26)],fill='white')
        d.arc([xy(20,27),xy(28,34)],0,180,fill='white',width=max(1,round(s*1.5)))
    if preview:
        base='/usr/share/fonts/truetype/dejavu/'
        font=lambda size,bold=False:ImageFont.truetype(base+('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'),size)
        d.rounded_rectangle((54,52,1146,578),radius=30,outline='#e7e7e7',width=2)
        mark(90,83,2)
        d.text((200,90),'kraken.',font=font(60,True),fill=ink)
        d.text((98,244),'Анализ ТЗ и КП',font=font(61,True),fill=ink)
        d.text((100,332),'Сравнивайте поставщиков по требованиям,',font=font(31),fill='#555555')
        d.text((100,378),'находите расхождения и проверяйте источники.',font=font(31),fill='#555555')
        d.rectangle((98,472,164,478),fill=red)
        d.text((100,501),'KRAKEN AI   /   ИНТЕЛЛЕКТУАЛЬНЫЕ ЗАКУПКИ',font=font(21,True),fill=red)
    else:
        mark(0,0,2)
    buf=io.BytesIO();im.save(buf,'PNG',optimize=True)
    return buf.getvalue()
