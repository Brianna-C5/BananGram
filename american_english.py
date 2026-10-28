"""American-English-focused game vocabulary filter.

CMUdict is an American pronunciation lexicon, not an official word-game list.
The UK-spelling exclusion set handles high-frequency dialect differences that
may appear in CMUdict. Some rare dialect variants remain ambiguous.
"""
import cmudict

# Alternate spellings typically used in British rather than American English.
# Do not ban spellings that are also ordinary American words (e.g. theatre as a
# proper name, metre as a specialized unit, or grey as a valid US variant).
BRITISH_SPELLINGS = frozenset("""
colour colours coloured colouring colourful colourless
favour favours favoured favouring favourite favourites favourable favourably
flavour flavours flavoured flavouring flavourful
honour honours honoured honouring honourable honourably
neighbour neighbours neighbouring neighbourly neighbourhood neighbourhoods
behaviour behaviours behavioural
labour labours laboured labouring labourer labourers
rumour rumours rumoured
humour humours humouring humourless
armour armoured armoury
vigour vigorous
valour
savour savoured savouring savoury
clamour clamoured clamouring
endeavour endeavours endeavoured endeavouring
harbour harbours harboured harbouring
mould moulds moulded moulding mouldy
smoulder smouldered smouldering
centre centres centred centring
litre litres millilitre millilitres kilometre kilometres centimetre centimetres
millimetre millimetres
fibre fibres fibrous
sabre sabres
organise organises organised organising organiser organisers organisation organisations
organisational
realise realises realised realising realisation realisations
recognise recognises recognised recognising
analyse analyses analysed analysing
paralyse paralysed paralysing
specialise specialises specialised specialising specialisation
apologise apologises apologised apologising
criticise criticises criticised criticising
civilise civilised civilising civilisation
advertiseable
traveller travellers travelling travelled
jewellery jeweller jewellers
cheque cheques
programme programmes
kerb kerbs
pyjamas
mum mums
aluminium
sulphur sulphurous
sulphate sulphates
sulphide sulphides
paediatric paediatrics paediatrician paediatricians
anaemia anaemic
oestrogen oestrogens
oesophagus oesophageal
aeroplane aeroplanes
manoeuvre manoeuvres manoeuvred manoeuvring
licence licences
practise practised practising
cosy cosier cosiest
storey storeys
plough ploughs ploughed ploughing
whilst amongst
maths
""".split())

# Load lazily once, after app startup, so all word checks share the same set.
_AMERICAN_WORDS = None


def is_american_english_word(word: str) -> bool:
    global _AMERICAN_WORDS
    if not word.isascii() or not word.isalpha():
        return False
    candidate = word.lower()
    if candidate in BRITISH_SPELLINGS:
        return False
    if _AMERICAN_WORDS is None:
        _AMERICAN_WORDS = set(cmudict.words())
    return candidate in _AMERICAN_WORDS
