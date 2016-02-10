#!/usr/bin/python
# -*- coding: utf-8


import re

e164CountryCodes = {
    '1242' : ('BS','Bahamas'),
    '1246' : ('BB','Barbados'),
    '1264' : ('AI','Anguilla'),
    '1268' : ('AG','Antigua and Barbuda'),
    '1284' : ('IVB','Territory of GB'),
    '1340' : ('ISV','Territory of US'),
    '1345' : ('KY','Cayman Islands'),
    '1441' : ('BM','Bermuda'),
    '1473' : ('GD','Grenada'),
    '1649' : ('TC','Turks and Caicos Islands'),
    '1664' : ('MS','Montserrat'),
    '1670' : ('MP','Northern Mariana Islands'),
    '1671' : ('GU','Guam'),
    '1684' : ('AS','American Samoa'),
    '1758' : ('LC','Saint Lucia'),
    '1767' : ('DM','Dominica'),
    '1784' : ('VC','Saint Vincent and the Grenadines'),
    '18091' : ('DO','Dominican Republic'),
    '18291' : ('DO','Dominican Republic'),
    '1849' : ('DO','Dominican Republic'),
    '1868' : ('TT','Trinidad and Tobago'),
    '1869' : ('KN','Saint Kitts and Nevis'),
    '1876' : ('JM','Jamaica'),
    '1' : ('US','United States'), # and Canada
    '20' : ('EG','Egypt'),
    '211' : ('SS','South Sudan'),
    '212' : ('EH','Western Sahara'),
    '212' : ('MA','Morocco'),
    '213' : ('DZ','Algeria'),
    '216' : ('TN','Tunisia'),
    '218' : ('LY','Libya'),
    '220' : ('GM','Gambia'),
    '221' : ('SN','Senegal'),
    '222' : ('MR','Mauritania'),
    '223' : ('ML','Mali'),
    '224' : ('GN','Guinea'),
    '225' : ('CI','Côte d\'Ivoire'),
    '226' : ('BF','Burkina Faso'),
    '227' : ('NE','Niger'),
    '228' : ('TG','Togo'),
    '229' : ('BJ','Benin'),
    '230' : ('MU','Mauritius'),
    '231' : ('LR','Liberia'),
    '232' : ('SL','Sierra Leone'),
    '233' : ('GH','Ghana'),
    '234' : ('NG','Nigeria'),
    '235' : ('TD','Chad'),
    '236' : ('CF','Central African Republic'),
    '237' : ('CM','Cameroon'),
    '238' : ('CV','Cape Verde'),
    '239' : ('ST','Sao Tome and Principe'),
    '240' : ('GQ','Equatorial Guinea'),
    '241' : ('GA','Gabon'),
    '242' : ('CG','Congo'),
    '243' : ('CD','Yes'),
    '244' : ('AO','Angola'),
    '245' : ('GW','Guinea-Bissau'),
    '246' : ('IO','British Indian Ocean Territory'),
    '248' : ('SC','Seychelles'),
    '249' : ('SD','Sudan'),
    '250' : ('RW','Rwanda'),
    '251' : ('ET','Ethiopia'),
    '252' : ('SO','Somalia'),
    '253' : ('DJ','Djibouti'),
    '254' : ('KE','Kenya'),
    '255' : ('TZ','Yes'),
    '256' : ('UG','Uganda'),
    '257' : ('BI','Burundi'),
    '258' : ('MZ','Mozambique'),
    '260' : ('ZM','Zambia'),
    '261' : ('MG','Madagascar'),
    '262' : ('RE','Réunion'),
    '262' : ('TF','French Southern Territories'),
    '262' : ('YT','Mayotte'),
    '263' : ('ZW','Zimbabwe'),
    '264' : ('NA','Namibia'),
    '265' : ('MW','Malawi'),
    '266' : ('LS','Lesotho'),
    '267' : ('BW','Botswana'),
    '268' : ('SZ','Swaziland'),
    '269' : ('KM','Comoros'),
    '27' : ('ZA','South Africa'),
    '290' : ('SH','Territory of GB'),
    '291' : ('ER','Eritrea'),
    '297' : ('AW','Aruba'),
    '298' : ('FO','Faroe Islands'),
    '299' : ('GL','Greenland'),
    '30' : ('GR','Greece'),
    '31' : ('NL','Netherlands'),
    '32' : ('BE','Belgium'),
    '33' : ('FR','France'),
    '34' : ('ES','Spain'),
    '350' : ('GI','Gibraltar'),
    '351' : ('PT','Portugal'),
    '352' : ('LU','Luxembourg'),
    '353' : ('IE','Ireland'),
    '354' : ('IS','Iceland'),
    '355' : ('AL','Albania'),
    '356' : ('MT','Malta'),
    '357' : ('CY','Cyprus'),
    '358' : ('AX','Åland Islands'),
    '358' : ('FI','Finland'),
    '359' : ('BG','Bulgaria'),
    '36' : ('HU','Hungary'),
    '370' : ('LT','Lithuania'),
    '371' : ('LV','Latvia'),
    '372' : ('EE','Estonia'),
    '373' : ('MD','Yes'),
    '374' : ('AM','Armenia'),
    '375' : ('BY','Belarus'),
    '376' : ('AD','Andorra'),
    '377' : ('MC','Monaco'),
    '378' : ('SM','San Marino'),
    '380' : ('UA','Ukraine'),
    '381' : ('SRB','Yes'),
    '382' : ('ME','Montenegro'),
    '385' : ('HR','Croatia'),
    '386' : ('SI','Slovenia'),
    '387' : ('BA','Bosnia and Herzegovina'),
    '389' : ('MK','Yes'),
    '3906' : ('VA','Holy See (Vatican City State)'),
    '39' : ('IT','Italy'),
    '40' : ('RO','Romania'),
    '41' : ('CH','Switzerland'),
    '420' : ('CZ','Czech Republic'),
    '421' : ('SK','Slovakia'),
    '423' : ('LI','Liechtenstein'),
    '43' : ('AT','Austria'),
    '44' : ('UK','United Kingdom'),
    '45' : ('DK','Denmark'),
    '46' : ('SE','Sweden'),
    '47' : ('NO','Norway'),
    '48' : ('PL','Poland'),
    '49' : ('DE','Germany'),
    '500' : ('FK','Falkland Islands (Malvinas)'),
    '501' : ('BZ','Belize'),
    '502' : ('GT','Guatemala'),
    '503' : ('SV','El Salvador'),
    '504' : ('HN','Honduras'),
    '505' : ('NI','Nicaragua'),
    '506' : ('CR','Costa Rica'),
    '507' : ('PA','Panama'),
    '508' : ('PM','Saint Pierre and Miquelon'),
    '509' : ('HT','Haiti'),
    '51' : ('PE','Peru'),
    '52' : ('MX','Mexico'),
    '53' : ('CU','Cuba'),
    '54' : ('AR','Argentina'),
    '55' : ('BR','Brazil'),
    '56' : ('CL','Chile'),
    '57' : ('CO','Colombia'),
    '58' : ('VE','Yes'),
    '590' : ('GP','Guadeloupe'),
    '590' : ('MF','Saint Martin (French part)'),
    '591' : ('BO','Yes'),
    '592' : ('GY','Guyana'),
    '593' : ('EC','Ecuador'),
    '594' : ('GF','French Guiana'),
    '595' : ('PY','Paraguay'),
    '596' : ('MQ','Martinique'),
    '597' : ('SR','Suriname'),
    '598' : ('UY','Uruguay'),
    '599' : ('AHO','840'),
    '60' : ('MY','Malaysia'),
    '61' : ('AU','Australia'),
    '62' : ('ID','Indonesia'),
    '63' : ('PH','Philippines'),
    '64' : ('NZ','New Zealand'),
    '65' : ('SG','Singapore'),
    '66' : ('TH','Thailand'),
    '670' : ('TL','Timor-Leste'),
    '672' : ('AQ','Antarctica'),
    '673' : ('BN','Brunei Darussalam'),
    '674' : ('NR','Nauru'),
    '675' : ('PG','Papua New Guinea'),
    '676' : ('TO','Tonga'),
    '677' : ('SB','Solomon Islands'),
    '678' : ('VU','Vanuatu'),
    '679' : ('FJ','Fiji'),
    '680' : ('PW','Palau'),
    '681' : ('WF','Wallis and Futuna'),
    '682' : ('CK','Cook Islands'),
    '683' : ('NU','Niue'),
    '685' : ('WS','Samoa'),
    '686' : ('KI','Kiribati'),
    '687' : ('NC','New Caledonia'),
    '688' : ('TV','Tuvalu'),
    '689' : ('PF','French Polynesia'),
    '690' : ('TK','Tokelau'),
    '691' : ('FM','Yes'),
    '692' : ('MH','Marshall Islands'),
    '7' : ('RU','Russian Federation'),
    '81' : ('JP','Japan'),
    '82' : ('KOR','410'),
    '84' : ('VN','Viet Nam'),
    '850' : ('PRK','408'),
    '852' : ('HK','Hong Kong'),
    '853' : ('MO','Macao'),
    '855' : ('KH','Cambodia'),
    '856' : ('LA','Lao People\'s Democratic Republic'),
    '86' : ('CN','China'),
    '870' : ('PN','Pitcairn'),
    '880' : ('BD','Bangladesh'),
    '886' : ('TW','Yes'),
    '90' : ('TR','Turkey'),
    '91' : ('IN','India'),
    '92' : ('PK','Pakistan'),
    '93' : ('AF','Afghanistan'),
    '94' : ('LK','Sri Lanka'),
    '95' : ('MM','Myanmar'),
    '960' : ('MV','Maldives'),
    '961' : ('LB','Lebanon'),
    '962' : ('JO','Jordan'),
    '963' : ('SY','Syrian Arab Republic'),
    '964' : ('IQ','Iraq'),
    '965' : ('KW','Kuwait'),
    '966' : ('SA','Saudi Arabia'),
    '967' : ('YE','Yemen'),
    '968' : ('OM','Oman'),
    '970' : ('PLE','No universal currency'),
    '971' : ('AE','United Arab Emirates'),
    '972' : ('IL','Israel'),
    '973' : ('BH','Bahrain'),
    '974' : ('QA','Qatar'),
    '975' : ('BT','Bhutan'),
    '976' : ('MN','Mongolia'),
    '977' : ('NP','Nepal'),
    '98' : ('IR','Yes'),
    '992' : ('TJ','Tajikistan'),
    '993' : ('TM','Turkmenistan'),
    '994' : ('AZ','Azerbaijan'),
    '995' : ('GE','Georgia'),
    '996' : ('KG','Kyrgyzstan'),
    '998' : ('UZ','Uzbekistan'),
}





nchars = re.compile('[^0-9\+]+')

# returns (e164 country code, remainder of number, iso country code, country name)
def num2codes(num):

    if not num:
        return None

    n = nchars.sub('', num)

    if len(n) < 8: return None

    if n.startswith('+'): n = n[1:]
    elif n.startswith('011'): n = n[3:]
    elif n.startswith('001'): n = n[3:]
    elif n.startswith('00'): n = n[2:]
    elif n.startswith('0'): n = n[1:]

    if len(n) < 8: return None

    cc = None
    nn = None

    for i in range(1, min(5, len(num)-6)):

        if n[0:i] in e164CountryCodes:
            cc = n[0:i]
            nn = n[i:]

    if cc: 
        d1 = e164CountryCodes[cc]
        return (cc, nn, d1[0], d1[1])

    else:
        return None





uspm = re.compile('^((\+1)|1)?\\d{10}$')

# this is too lax .. just checks for 10 digits
def isUSdomesticNumber(num):
    if num == None: return False
    return uspm.match(num) != None

# check if number is valid and we can match a country code
def isInterationalNumber(num):

    if not looksLikeValidPSTNnumber(num):
        return False

    if isUSdomesticNumber(num): return False

    if num.startswith('+1') or num.startswith('1'): return False
    return len(num) > 9



def looksLikeValidPSTNnumber(num):

    if not num or len(num) < 8:
        return False

    num = nchars.sub('', num)

    if len(num) < 8:
        return False

    c = num2codes(num)

    return c != None and len(c[1]) >= 6


###############################################################################
## {{{ py.test tests


def test_nc1():

    c = num2codes('+44123400067')
    assert c[0] == '44'
    assert c[1] == '123400067'
    assert c[2] == 'UK'
    assert c[3] == 'United Kingdom'

    c = num2codes('14512345670')
    assert c[0] == '1'
    assert c[1] == '4512345670'
    assert c[2] == 'US'

    c = num2codes('+12122345678')
    assert c[0] == '1'
    assert c[1] == '2122345678'
    assert c[2] == 'US'

    # could be a US number, but is actually outlying territories
    c = num2codes('+16642223333')
    assert c[0] == '1664'
    assert c[1] == '2223333'
    assert c[2] == 'MS'

    c = num2codes('0115527642223333')
    assert c[0] == '55'
    assert c[1] == '27642223333'
    assert c[2] == 'BR'


def test_c2():

    n = '18763988463'
    c = num2codes(n)
    assert c[2] == 'JM'

    c = num2codes('1 (503) 645-9751')
    assert c[0] == '1'
    assert c[1] == '5036459751'
    assert c[2] == 'US'

def test_looks_valid():

    assert looksLikeValidPSTNnumber('+44123400067')
    assert looksLikeValidPSTNnumber('01144123400067')
    assert looksLikeValidPSTNnumber('1 (503) 645-9751')

    assert not looksLikeValidPSTNnumber('0113334445')
    assert not looksLikeValidPSTNnumber('anonymous')
    assert not looksLikeValidPSTNnumber('0533-999')

def test_is_domestic_or_intl():

    assert isInterationalNumber('00528182436554')
    assert not isUSdomesticNumber('00528182436554')

## }}}
###############################################################################

if __name__ == '__main__':

    test_nc1()
