#!/usr/bin/env python3
"""
Complete House of Representatives database with all 360 members.
This script adds remaining states to the index and generates all member files.
"""

import json
from pathlib import Path

base_dir = Path("/Users/Admin/Decide9ja/decide9ja_scraper/data/candidates/house_of_reps")

# Additional states data (Ekiti through Zamfara)
additional_states = {
    "Ekiti": {
        "count": 6,
        "members": [
            {"constituency": "Ido/Osi/Moba/Ilejemeje", "name": "Akinlayo Kolawole Davidson", "party": "APC"},
            {"constituency": "Ikole/Oye Ekiti", "name": "Rotimi Akindele Oluwaseun", "party": "APC"},
            {"constituency": "Emure/Gbonyin/Ekiti East", "name": "Bamidele Olufemi Richard", "party": "APC"},
            {"constituency": "Ijero/Ekiti West/Efon", "name": "Omoyele Abiodun Francis", "party": "APC"},
            {"constituency": "Ado Ekiti/Ifelodun", "name": "Oluwafemi Victor Fatoba", "party": "APC"},
            {"constituency": "Ekiti South West/Ikere/Ise-Orun", "name": "Ojuawo Rufus Adeniyi", "party": "APC"}
        ]
    },
    "Enugu": {
        "count": 8,
        "members": [
            {"constituency": "Igbo Eze North/Udenu", "name": "Agbo Nnamdi Dennis", "party": "PDP"},
            {"constituency": "Nsukka/Igbo-Eze South", "name": "Chidi Mark Obetta", "party": "PDP"},
            {"constituency": "Enugu North/Enugu South", "name": "Sam Chimaobi Atu", "party": "LP"},
            {"constituency": "Igbo-Etiti/Uzo-Uwani", "name": "Chijioke Stainless Nwodo", "party": "LP"},
            {"constituency": "Ezeagu/Udi", "name": "Cyracus Sunday Umeha", "party": "LP"},
            {"constituency": "Aninri/Awgu/Oji River", "name": "Anayo Onwuegbu Befford", "party": "PDP"},
            {"constituency": "Nkanu East/Nkanu West", "name": "Nnolim John Nnaji", "party": "LP"},
            {"constituency": "Enugu East/Isi-Uzo", "name": "Martins George Oke", "party": "LP"}
        ]
    },
    "Gombe": {
        "count": 6,
        "members": [
            {"constituency": "Gombe/Kwami/Funakaye", "name": "Yaya Bauchi Tongo", "party": "APC"},
            {"constituency": "Kaltungo/Shongom", "name": "Paul Obed Shehu", "party": "APC"},
            {"constituency": "Dukku/Nafada", "name": "El-Rasheed Abdullahi", "party": "APC"},
            {"constituency": "Akko", "name": "Usman Bello Kumo", "party": "APC"},
            {"constituency": "Balanga/Billiri", "name": "Ali Isa", "party": "PDP"},
            {"constituency": "Yamaltu-Deba", "name": "Inuwa Garba Yamaltu", "party": "APC"}
        ]
    },
    "Imo": {
        "count": 10,
        "members": [
            {"constituency": "Aboh Mbaise/Ngor Okpala", "name": "Nwogu Kelechi", "party": "LP"},
            {"constituency": "Ehime Mbano/Ihitte Uboma/Obowo", "name": "Okafor Emeka", "party": "APC"},
            {"constituency": "Ideato North/Ideato South", "name": "Ugochinyere Ikeagwuonu", "party": "PDP"},
            {"constituency": "Oru East/Orsu/Orlu", "name": "Nwachukwu Emeka", "party": "APC"},
            {"constituency": "Owerri Municipal/Owerri North/Owerri West", "name": "Okere Kingsley", "party": "LP"},
            {"constituency": "Onuimo/Okigwe/Isiala Mbano", "name": "Onuoha Chijindu", "party": "APC"},
            {"constituency": "Oguta/Ohaji-Egbema/Oru West", "name": "Emeka Atuma", "party": "APC"},
            {"constituency": "Mbaitoli/Ikeduru", "name": "Henry Nwawuba", "party": "LP"},
            {"constituency": "Nkwerre/Isu/Njaba/Nwangele", "name": "Miriam Onuoha", "party": "APC"},
            {"constituency": "Ahiazu Mbaise/Ezinihitte", "name": "Chidoka Obika", "party": "LP"}
        ]
    },
    "Jigawa": {
        "count": 11,
        "members": [
            {"constituency": "Hadejia/Auyo/Kafin Hausa", "name": "Ibrahim Usman Auyo", "party": "APC"},
            {"constituency": "Dutse/Kiyawa", "name": "Dahiru Musa", "party": "PDP"},
            {"constituency": "Kazaure/Roni/Gwiwa/Yankwashi", "name": "Muhammad Kazaure", "party": "APC"},
            {"constituency": "Jahun/Miga", "name": "Yusuf Adamu", "party": "APC"},
            {"constituency": "Gwaram", "name": "Galambi Ibrahim", "party": "NNPP"},
            {"constituency": "Birnin Kudu/Buji", "name": "Yakubu Shehu", "party": "PDP"},
            {"constituency": "Birniwa/Guri/Kiri Kasamma", "name": "Fulata Abubakar", "party": "APC"},
            {"constituency": "Mallam-Madori/Kaugama", "name": "Abubakar Suleiman", "party": "APC"},
            {"constituency": "Ringim/Taura", "name": "Aminu Suleiman", "party": "APC"},
            {"constituency": "Gumel/Gagarawa/Maigatari/Sule Tankarkar", "name": "Murtala Musa", "party": "NNPP"},
            {"constituency": "Babura/Garki", "name": "Haruna Ibrahim", "party": "APC"}
        ]
    },
    "Kaduna": {
        "count": 16,
        "members": [
            {"constituency": "Kaduna South", "name": "Abdulkarim Ahmed", "party": "PDP"},
            {"constituency": "Sabon Gari", "name": "Abdullahi Ango", "party": "PDP"},
            {"constituency": "Makarfi/Kudan", "name": "Shehu Umar Ajilo", "party": "PDP"},
            {"constituency": "Ikara/Kubau", "name": "Abdullahi Mustapha Aliyu", "party": "PDP"},
            {"constituency": "Jema'a/Sanga", "name": "Daniel Amos", "party": "PDP"},
            {"constituency": "Kaduna North", "name": "Bello Mohammed El-Rufai", "party": "APC"},
            {"constituency": "Igabi", "name": "Mohammed Hussaini Jallo", "party": "PDP"},
            {"constituency": "Zangon Kataf/Jaba", "name": "Magaji Abel", "party": "PDP"},
            {"constituency": "Giwa/Birnin Gwari", "name": "Usman Bashir Zubairu", "party": "APC"},
            {"constituency": "Chikun/Kajuru", "name": "Adams Abubakar Ekene", "party": "PDP"},
            {"constituency": "Soba", "name": "Richifa Suleiman Yahaya", "party": "PDP"},
            {"constituency": "Kauru", "name": "Bashir Yusuf", "party": "PDP"},
            {"constituency": "Lere", "name": "Mohammed Ahmed Munir", "party": "PDP"},
            {"constituency": "Kaura", "name": "Kuzalio Donatus Matthew", "party": "PDP"},
            {"constituency": "Zaria", "name": "Tajudeen Abbas", "party": "APC"},
            {"constituency": "Kagarko/Kachia", "name": "Mohammed Alfa", "party": "PDP"}
        ]
    },
    "Kano": {
        "count": 24,
        "members": [
            {"constituency": "Wudil/Garko", "name": "Abdulhakeem Kamilu Ado", "party": "NNPP"},
            {"constituency": "Sumaila/Takai", "name": "Rabiu Yusuf", "party": "NNPP"},
            {"constituency": "Kumbotso", "name": "Idris Dankawu", "party": "NNPP"},
            {"constituency": "Nassarawa", "name": "Hussain Hassan Shehu", "party": "NNPP"},
            {"constituency": "Ungogo/Minjibir", "name": "Sani Adamu", "party": "NNPP"},
            {"constituency": "Karaye/Rogo", "name": "Rogo Abdullahi Sani", "party": "NNPP"},
            {"constituency": "Gezawa/Gabasawa", "name": "Garba Mohammed Chiroma", "party": "NNPP"},
            {"constituency": "Kiru/Bebeji", "name": "Abdulmumin Jibrin", "party": "NNPP"},
            {"constituency": "Ajingi/Gaya/Albasu", "name": "Ghali Tijjani Mustapha", "party": "NNPP"},
            {"constituency": "Dawakin Tofa/Tofa/Rimin Gado", "name": "Tijjani Abdulkadir Jobe", "party": "NNPP"},
            {"constituency": "Rano/Bunkure/Kibiya", "name": "Kabiru Alhassan Usman Rurum", "party": "NNPP"},
            {"constituency": "Tsanyawa/Kunchi", "name": "Umar Sani Bala", "party": "NNPP"},
            {"constituency": "Tarauni", "name": "Zakari Mukhtari Umar", "party": "NNPP"},
            {"constituency": "Municipal", "name": "Ibrahim Sagir Koki", "party": "NNPP"},
            {"constituency": "Kura/Madobi/Garun Mallam", "name": "Umar Yusuf Datti", "party": "NNPP"},
            {"constituency": "Gwale", "name": "Ibrahim Garba Mohammed", "party": "NNPP"},
            {"constituency": "Kabo/Gwarzo", "name": "Gwarzo Abdullahi Mu'azu", "party": "NNPP"},
            {"constituency": "Dala", "name": "Tijjani Ibrahim Aliyu", "party": "NNPP"},
            {"constituency": "Fagge", "name": "Ahmed Garba Bichi", "party": "APC"},
            {"constituency": "Makoda/Dambatta", "name": "Kabiru Ibrahim Dambatta", "party": "APC"},
            {"constituency": "Shanono/Bagwai", "name": "Mahmud Sani Shanono", "party": "APC"},
            {"constituency": "Minjibir/Dawakin Kudu", "name": "Kabiru Ishaku", "party": "NNPP"},
            {"constituency": "Tudun Wada/Doguwa", "name": "Abubakar Sadiq", "party": "APC"},
            {"constituency": "Warawa/Kabo", "name": "Aliyu Madaki", "party": "NNPP"}
        ]
    },
    "Katsina": {
        "count": 15,
        "members": [
            {"constituency": "Dutsin-Ma/Kurfi", "name": "Aminu Balele", "party": "APC"},
            {"constituency": "Daura/Sandamu/Mai'Adua", "name": "Aminu Jamo", "party": "APC"},
            {"constituency": "Bindawa/Mani", "name": "Ahmed Yusuf Doro", "party": "APC"},
            {"constituency": "Bakori/Danja", "name": "Balarabe Abdullahi Dabai", "party": "PDP"},
            {"constituency": "Safana/Batsari/Dan Musa", "name": "Abubakar Aliyu Iliyasu", "party": "PDP"},
            {"constituency": "Katsina", "name": "Chindo Aminu Ahmad", "party": "APC"},
            {"constituency": "Musawa/Matazu", "name": "Abdullahi Aliyu Ahmed", "party": "APC"},
            {"constituency": "Kankia/Ingawa/Kusada", "name": "Kusada Ismail Dalha", "party": "APC"},
            {"constituency": "Mashi/Dutsi", "name": "Majigiri Salisu Yusuf", "party": "APC"},
            {"constituency": "Funtua/Dandume", "name": "Ahmad Abubakar Mohammad", "party": "APC"},
            {"constituency": "Kankara/Faskari/Sabuwa", "name": "Jamilu Mohammed", "party": "APC"},
            {"constituency": "Rimi/Charanchi/Batagarawa", "name": "Banye Usman Murtala", "party": "APC"},
            {"constituency": "Baure/Zango", "name": "Sani Lawal", "party": "APC"},
            {"constituency": "Kaita/Jibia", "name": "Sada Soli", "party": "APC"},
            {"constituency": "Malumfashi/Kafur", "name": "Yusuf Sunusi Isa", "party": "APC"}
        ]
    },
    "Kebbi": {
        "count": 8,
        "members": [
            {"constituency": "Argungu/Augie", "name": "Noma Yakubu Sani", "party": "APC"},
            {"constituency": "Aleiro/Gwandu/Jega", "name": "Musa Mansur", "party": "PDP"},
            {"constituency": "Fakai/Sakaba/Wasagu-Danko/Zuru", "name": "Kabir Tukura Ibrahim", "party": "APC"},
            {"constituency": "Bagudo/Suru", "name": "Bello A. Kaoje", "party": "APC"},
            {"constituency": "Maiyama/Koko-Besse", "name": "Shehu Mohammed", "party": "APC"},
            {"constituency": "Arewa/Dandi", "name": "Umar Abdullahi Kamba", "party": "PDP"},
            {"constituency": "Birnin Kebbi/Kalgo/Bunza", "name": "Muhammad Bello Yakubu", "party": "APC"},
            {"constituency": "Yauri/Ngaski/Shanga", "name": "Abubakar Isah", "party": "APC"}
        ]
    },
    "Kogi": {
        "count": 9,
        "members": [
            {"constituency": "Lokoja/Kogi", "name": "Danladi Suleiman Aguya", "party": "APC"},
            {"constituency": "Okene/Ogori-Magongo", "name": "Tijani Muhammed Ozigi", "party": "APC"},
            {"constituency": "Kabba-Bunu/Ijumu", "name": "Salman Idris", "party": "APC"},
            {"constituency": "Adavi/Okehi", "name": "Danga Abdulraheem Abdulmaleek", "party": "PDP"},
            {"constituency": "Ajaokuta", "name": "Abdulraheem Egide Sanni", "party": "APC"},
            {"constituency": "Yagba East/Yagba West/Mopa Muro", "name": "Leke Joseph Abejide", "party": "APC"},
            {"constituency": "Idah/Igalamela Odolu/Ibaji/Ofu", "name": "David Idris Zacharias", "party": "APC"},
            {"constituency": "Ankpa/Omala/Olamaboro", "name": "Ali Ibrahim Abdullahi", "party": "APC"},
            {"constituency": "Dekina/Bassa", "name": "Haruna Paul Gowon", "party": "APC"}
        ]
    },
    "Kwara": {
        "count": 6,
        "members": [
            {"constituency": "Ilorin East/Ilorin South", "name": "Yinka Ahmed Aluko", "party": "APC"},
            {"constituency": "Ilorin West/Asa", "name": "Tolani Shagaya", "party": "APC"},
            {"constituency": "Ekiti/Isin/Irepodun/Oke-Ero", "name": "Tunji Raheem Olawuyi", "party": "APC"},
            {"constituency": "Edu/Moro/Pategi", "name": "Adam Ahmed Saba", "party": "APC"},
            {"constituency": "Baruten/Kaiama", "name": "Mohammed Omar Bio", "party": "APC"},
            {"constituency": "Ifelodun/Offa/Oyun", "name": "Ismail Kayode Tijani", "party": "APC"}
        ]
    },
    "Lagos": {
        "count": 24,
        "members": [
            {"constituency": "Agege", "name": "Hameed Adewale Waheed", "party": "APC"},
            {"constituency": "Ajeromi/Ifelodun", "name": "Kalejaiye Adeboye", "party": "APC"},
            {"constituency": "Alimosho", "name": "Ganiyu Ayuba", "party": "APC"},
            {"constituency": "Amuwo-Odofin", "name": "George Adegeye", "party": "LP"},
            {"constituency": "Badagry", "name": "Sesi Whingah", "party": "APC"},
            {"constituency": "Epe", "name": "Raji Olawale", "party": "APC"},
            {"constituency": "Eti-Osa", "name": "Thaddeus Attah", "party": "LP"},
            {"constituency": "Mushin I", "name": "Alli Taofik", "party": "APC"},
            {"constituency": "Kosofe", "name": "Kafilat Adetola Ogbara", "party": "APC"},
            {"constituency": "Apapa", "name": "Olumuyiwa Adesola Samuel Adedayo", "party": "APC"},
            {"constituency": "Lagos Mainland", "name": "Oshun Moshood Olanrewaju", "party": "APC"},
            {"constituency": "Ikorodu", "name": "Babajimi Adegoke Benson", "party": "APC"},
            {"constituency": "Lagos Island II", "name": "Moshood Kayode Akiolu", "party": "APC"},
            {"constituency": "Oshodi/Isolo I", "name": "Bashiru Ayinla Dawodu", "party": "APC"},
            {"constituency": "Shomolu", "name": "Aliu Ademorin Kuye", "party": "APC"},
            {"constituency": "Ifako/Ijaiye", "name": "Benjamin Adeyemi Olabinjo", "party": "APC"},
            {"constituency": "Oshodi-Isolo II", "name": "Okey-joe Onaukalusi", "party": "LP"},
            {"constituency": "Ibeju-Lekki", "name": "Oluwaseyi Ayopo", "party": "APC"},
            {"constituency": "Surulere II", "name": "Lanre Okunlola", "party": "APC"},
            {"constituency": "Lagos Island I", "name": "Enitan Dolapo-Badru", "party": "APC"},
            {"constituency": "Ikeja", "name": "James Faleke", "party": "APC"},
            {"constituency": "Surulere I", "name": "Fuad Laguda", "party": "APC"},
            {"constituency": "Mushin II", "name": "Akinwunmi Fatai", "party": "APC"},
            {"constituency": "Ojo", "name": "Victor Akande", "party": "APC"}
        ]
    },
    "Nasarawa": {
        "count": 5,
        "members": [
            {"constituency": "Lafia/Obi", "name": "Dahiru Sariki Abubakar", "party": "SDP"},
            {"constituency": "Akwanga/Nasarawa Egon/Wamba", "name": "Jeremiah Umaru", "party": "APC"},
            {"constituency": "Keffi/Karu/Kokona", "name": "Gaza Jonathan Gbefwi", "party": "SDP"},
            {"constituency": "Awe/Doma/Keana", "name": "Abubakar Hassan Nalaraba", "party": "APC"},
            {"constituency": "Nasarawa/Toto", "name": "Abdulmumin Ari Mohammed", "party": "APC"}
        ]
    },
    "Niger": {
        "count": 10,
        "members": [
            {"constituency": "Agaie/Lapai", "name": "Abdullahi Mamudu", "party": "APC"},
            {"constituency": "Gbako/Bida/Katcha", "name": "Abdullahi Saidu Musa", "party": "APC"},
            {"constituency": "Bosso/Paikoro", "name": "Abubakar Abdul Buba Abubakar", "party": "APC"},
            {"constituency": "Chanchaga/Lavun", "name": "Baraje Yusuf Kure", "party": "APC"},
            {"constituency": "Mokwa/Edati", "name": "Gana Joshua Audu", "party": "APC"},
            {"constituency": "Kontagora/Wushishi/Mariga/Mashegu", "name": "Garba Idris Abdullahi", "party": "APC"},
            {"constituency": "Shiroro/Rafi/Munya", "name": "Modibo Ismail Musa", "party": "APC"},
            {"constituency": "Borgu/Magama", "name": "Mohammed Jafara Ali", "party": "APC"},
            {"constituency": "Rijau/Borgu", "name": "Saleh Shehu Rijau", "party": "APC"},
            {"constituency": "Gurara/Suleja/Tafa", "name": "Tanko Adamu", "party": "PDP"}
        ]
    },
    "Ogun": {
        "count": 9,
        "members": [
            {"constituency": "Ijebu Ode/Odogbolu/Ijebu North East", "name": "Olufemi Adeleke Ogunbanwo", "party": "APC"},
            {"constituency": "Ijebu North/Ijebu East/Ogun Waterside", "name": "Folorunsho Joseph Adegbesan", "party": "APC"},
            {"constituency": "Egbado South/Ipokia", "name": "Isiaq Abiodun Akinlade", "party": "APC"},
            {"constituency": "Abeokuta South", "name": "Moruf Afolabi Afuape", "party": "APC"},
            {"constituency": "Abeokuta North", "name": "Akanni Olatunji Akinosi", "party": "APC"},
            {"constituency": "Egbado North/Imeko Afon", "name": "Adegboyega Nasiru Isiaka", "party": "APC"},
            {"constituency": "Ifo/Ewekoro", "name": "Ibrahim Ayokunle Isiaka", "party": "APC"},
            {"constituency": "Obafemi Owode/Odeda", "name": "Olumide Babatunde Osoba", "party": "APC"},
            {"constituency": "Ado-Odo/Ota", "name": "Jimoh Olusola Ojugbele", "party": "APC"}
        ]
    },
    "Ondo": {
        "count": 9,
        "members": [
            {"constituency": "Okitipupa/Irele", "name": "John Okunjimi Odimayo", "party": "APC"},
            {"constituency": "Ese Odo/Ilaje", "name": "Kimikanboh Donald Ojogo", "party": "APC"},
            {"constituency": "Ile Oluji-Okeigbo/Odigbo", "name": "Festus Ayodele Adefiranye", "party": "APC"},
            {"constituency": "Idanre/Ifedore", "name": "Olanrewaju Festus Akingbaso", "party": "APC"},
            {"constituency": "Akure North/Akure South", "name": "Abiodun Aderin Adesida", "party": "APC"},
            {"constituency": "Ondo East/Ondo West", "name": "Abiola Peter Makinde", "party": "APC"},
            {"constituency": "Akoko North East/Akoko North West", "name": "Olubunmi Tunji-Ojo", "party": "APC"},
            {"constituency": "Owo/Ose", "name": "Adelegbe Emmanuel Oluwatimehin", "party": "APC"},
            {"constituency": "Akoko South East/Akoko South West", "name": "Adegboyega Adeyemi Adefarati", "party": "APC"}
        ]
    },
    "Osun": {
        "count": 9,
        "members": [
            {"constituency": "Odo-Otin/Ifelodun/Boripe", "name": "Olusoji Abidemi Adetunji", "party": "PDP"},
            {"constituency": "Irepodun/Olorunda/Osogbo/Orolu", "name": "Adebayo Morufu Adewale", "party": "PDP"},
            {"constituency": "Boluwaduro/Ifedayo/Ila", "name": "Ademola Clement Akanni", "party": "PDP"},
            {"constituency": "Ayedire/Iwo/Ola-Oluwa", "name": "Alani Lukman Mudashiru", "party": "PDP"},
            {"constituency": "Atakunmosa East/Atakunmosa West/Ilesa", "name": "Olusanya Emmanuel Omirin", "party": "PDP"},
            {"constituency": "Ife Central/Ife North/Ife South/Ife East", "name": "Taofeek Abimbola Ajilesoro", "party": "PDP"},
            {"constituency": "Obokun/Oriade", "name": "Oluwole Busayo Oke", "party": "PDP"},
            {"constituency": "Ede North/Ede South/Egbedore/Ejigbo", "name": "Bamidele Salam", "party": "PDP"},
            {"constituency": "Ayedaade/Irewole/Isokan", "name": "Oladebo Lanre Olomololaye", "party": "PDP"}
        ]
    },
    "Oyo": {
        "count": 14,
        "members": [
            {"constituency": "Ibadan North-East/South-East", "name": "Abass Adekunle Adigun", "party": "PDP"},
            {"constituency": "Ogo-Oluwa/Surulere", "name": "Makanjuola Sunday Ojo", "party": "APC"},
            {"constituency": "Iseyin/Itesiwaju/Kajola/Iwajowa", "name": "Oyeshina Najimdeen Oyedeji", "party": "APC"},
            {"constituency": "Ibarapa Central/Ibarapa North", "name": "Adebayo Anthony Adepoju", "party": "APC"},
            {"constituency": "Irepo/Orelope/Olorunsogo", "name": "Lateef Olaide Mohammed", "party": "APC"},
            {"constituency": "Ibarapa East/Ido", "name": "Aderemi Abasi Oseni", "party": "APC"},
            {"constituency": "Akinyele/Lagelu", "name": "Wasiu Olafisoye Akinmoyede", "party": "APC"},
            {"constituency": "Egbeda/Ona-Ara", "name": "Akinola Alabi", "party": "APC"},
            {"constituency": "Atisbo/Saki East/Saki West", "name": "Kareem Tajudeen Abisodun", "party": "APC"},
            {"constituency": "Ibadan North", "name": "Prince Olaide Adewale Akinremi", "party": "APC"},
            {"constituency": "Afijio/Atiba/Oyo East/Oyo West", "name": "Akeem Adeniyi Adeyemi", "party": "APC"},
            {"constituency": "Ibadan South West/Ibadan North West", "name": "Adedeji Stanley Olajide", "party": "APC"},
            {"constituency": "Oluyole", "name": "Tolulope Akande-Sadipe", "party": "APC"},
            {"constituency": "Ogbomosho North/Ogbomosho South/Oriire", "name": "Olumide Oseni", "party": "APC"}
        ]
    },
    "Plateau": {
        "count": 8,
        "members": [
            {"constituency": "Bassa/Jos North", "name": "Daniel Asama", "party": "LP"},
            {"constituency": "Barkin Ladi/Riyom", "name": "Fom Dalyop Chollom", "party": "LP"},
            {"constituency": "Jos South/Jos East", "name": "Ajang Alfred Illiya", "party": "LP"},
            {"constituency": "Langtang North/Langtang South", "name": "Bulus Vincent Venman", "party": "APC"},
            {"constituency": "Mikang/Qua'an Pan/Shendam", "name": "John Moenwul Dafa'an", "party": "APC"},
            {"constituency": "Pankshin/Kanke/Kanam", "name": "Gagdi Adamu Yusuf", "party": "APC"},
            {"constituency": "Wase", "name": "Ahmed Idris", "party": "APC"},
            {"constituency": "Bokkos/Mangu", "name": "David Ishaya Lalu", "party": "LP"}
        ]
    },
    "Rivers": {
        "count": 13,
        "members": [
            {"constituency": "Okrika/Ogu-Bolo", "name": "Igbiks Allison Anderson", "party": "PDP"},
            {"constituency": "Port Harcourt I", "name": "Manuchim Umezuruike", "party": "LP"},
            {"constituency": "Degema/Bonny", "name": "Godwin Cyril Hart", "party": "PDP"},
            {"constituency": "Eleme/Oyigbo/Tai", "name": "Uche Felix Nwaeke", "party": "PDP"},
            {"constituency": "Ahoada West/Ogba-Egbema-Ndoni", "name": "Amadi Victor Chukwuemele Obuzor", "party": "PDP"},
            {"constituency": "Etche/Omuma", "name": "Kelechi Godspower Nwogu", "party": "PDP"},
            {"constituency": "Abua-Odual/Ahoada East", "name": "Solomon T. Bob", "party": "PDP"},
            {"constituency": "Obio-Akpor", "name": "Kingsley Ogundu Chinda", "party": "PDP"},
            {"constituency": "Ikwerre/Emuoha", "name": "Boniface Sunday Emerengwa", "party": "PDP"},
            {"constituency": "Akuku-Toru/Asari-Toru", "name": "Boma Goodhead", "party": "PDP"},
            {"constituency": "Andoni-Opobo/Nkoro", "name": "Awaji-Inombek Dagomie Abiante", "party": "PDP"},
            {"constituency": "Khana/Gokana", "name": "Dumnamene Robinson Dekor", "party": "PDP"},
            {"constituency": "Port Harcourt II", "name": "Blessing Amadi", "party": "PDP"}
        ]
    },
    "Sokoto": {
        "count": 11,
        "members": [
            {"constituency": "Sokoto North/Sokoto South", "name": "Abubakar Abdullahi Ahmad", "party": "APC"},
            {"constituency": "Illela/Gwadabawa", "name": "Isah Bello Ambarura", "party": "APC"},
            {"constituency": "Dange-Shuni/Bodinga/Tureta", "name": "Nasiru Shehu Bodinga", "party": "APC"},
            {"constituency": "Goronyo/Gada", "name": "Bashir Usman Gorau", "party": "PDP"},
            {"constituency": "Isa/Sabon Birni", "name": "Mohammed Saidu Bargaja", "party": "PDP"},
            {"constituency": "Wamakko/Kware/Silame", "name": "Abdussamad Ibrahim Dasuki", "party": "APC"},
            {"constituency": "Tangaza/Gudu", "name": "Aliyu Ibrahim Almustapha", "party": "APC"},
            {"constituency": "Kebbe/Tambuwal", "name": "Yakubu Sani Alhaji", "party": "PDP"},
            {"constituency": "Yabo/Shagari", "name": "Yusuf Umar Yabo", "party": "APC"},
            {"constituency": "Wurno/Rabah", "name": "Mani Maishinko Katami", "party": "APC"},
            {"constituency": "Binji/Salame", "name": "Abdullahi Ahmad Kalambaina", "party": "APC"}
        ]
    },
    "Taraba": {
        "count": 6,
        "members": [
            {"constituency": "Sardauna/Kurmi/Gashaka", "name": "Abel David Fuoh", "party": "PDP"},
            {"constituency": "Karim Lamido/Lau/Ardo-Kola", "name": "Audu Mohammed Lauya", "party": "PDP"},
            {"constituency": "Bali/Gassol", "name": "Jafaru Yakubu", "party": "PDP"},
            {"constituency": "Jalingo/Yorro/Zing", "name": "Sadiq Abbas Tafida", "party": "PDP"},
            {"constituency": "Takum/Ussa/Donga", "name": "Husseni Mark Bako", "party": "PDP"},
            {"constituency": "Wukari/Ibi", "name": "Zaku Ayuba Aboki Dampar", "party": "PDP"}
        ]
    },
    "Yobe": {
        "count": 6,
        "members": [
            {"constituency": "Bursari/Geidam/Yunusari", "name": "Alli Shettima", "party": "APC"},
            {"constituency": "Damaturu/Gujba/Gulani/Tarmuwa", "name": "Khadija Bukar Abba Ibrahim", "party": "APC"},
            {"constituency": "Bade/Jakusko", "name": "Jakduwa Hassan Kaikaku", "party": "PDP"},
            {"constituency": "Fika/Fune", "name": "Mohammed Buba Jajere", "party": "PDP"},
            {"constituency": "Nangere/Potiskum", "name": "Fatima Talba", "party": "APC"},
            {"constituency": "Machina/Nguru/Yusufari/Karasuwa", "name": "Zakariya Tijjani Zannah", "party": "APC"}
        ]
    },
    "Zamfara": {
        "count": 7,
        "members": [
            {"constituency": "Anka/Talata Mafara", "name": "Mohammed Isa Anka", "party": "APC"},
            {"constituency": "Bakura/Maradun", "name": "Ahmad Sani Muhammed", "party": "APC"},
            {"constituency": "Bungudu/Maru", "name": "Shehu Ahmed", "party": "PDP"},
            {"constituency": "Kaura-Namoda/Birnin-Magaji", "name": "Aminu Sani Jaji", "party": "APC"},
            {"constituency": "Gusau/Tsafe", "name": "Kabiru Ahmadu Mai", "party": "PDP"},
            {"constituency": "Shinkafi/Zurmi", "name": "Hassan Bello Shinkafi", "party": "PDP"},
            {"constituency": "Talata Mafara/Gummi", "name": "Sani Ibrahim Musa", "party": "APC"}
        ]
    }
}

def create_filename(state, constituency):
    """Generate filename from state and constituency"""
    state_lower = state.lower().replace(" ", "_")
    const_lower = constituency.lower()
    const_lower = const_lower.replace("/", "_").replace(" ", "_").replace("-", "_").replace("'", "")
    # Clean up multiple underscores
    while "__" in const_lower:
        const_lower = const_lower.replace("__", "_")
    return f"{state_lower}_{const_lower}.json"

def create_member_data(state, member):
    """Create member JSON data"""
    name = member["name"]
    constituency = member["constituency"]
    party = member["party"]
    
    slug = name.lower().replace("'", "").replace(".", "").replace(" ", "-")
    name_parts = name.split()
    if len(name_parts) >= 2:
        id_str = f"{name_parts[-1].lower()}_{name_parts[0].lower()}"
    else:
        id_str = name.lower().replace(" ", "_")
    
    return {
        "id": id_str,
        "slug": slug,
        "state": state,
        "federal_constituency": constituency,
        "name": {
            "full": name,
            "common": name,
            "aliases": []
        },
        "party": party,
        "personal": {
            "date_of_birth": None,
            "state_of_origin": state,
            "lga_of_origin": None,
            "religion": None,
            "education": []
        },
        "political_career": {
            "positions_held": [
                {
                    "position": "Member, House of Representatives",
                    "constituency": f"{constituency} Federal Constituency",
                    "period": "2023-present"
                }
            ]
        },
        "house_info": {
            "committee_memberships": [],
            "bills_sponsored": [],
            "motions": [],
            "legislative_focus": []
        },
        "social_media": {
            "twitter": None,
            "facebook": None,
            "website": None
        },
        "metadata": {
            "data_quality_score": 0.45,
            "last_updated": "2025-12-27T21:35:00Z"
        }
    }

# Create files for additional states
created = 0
skipped = 0

for state, state_data in additional_states.items():
    for member in state_data["members"]:
        filename = create_filename(state, member["constituency"])
        filepath = base_dir / filename
        
        if filepath.exists():
            skipped += 1
            continue
        
        member_json = create_member_data(state, member)
        
        with open(filepath, "w") as f:
            json.dump(member_json, f, indent=2)
        
        created += 1
        print(f"Created: {filename}")

print(f"\nPhase 1 Done! Created: {created}, Skipped: {skipped}")

# Now update the index to include all states
print("\nUpdating index file...")

# Load current index
with open(base_dir / "_index.json", "r") as f:
    index_data = json.load(f)

# Add the additional states to the index
for state, state_data in additional_states.items():
    members_with_files = []
    for member in state_data["members"]:
        filename = create_filename(state, member["constituency"])
        members_with_files.append({
            "constituency": member["constituency"],
            "name": member["name"],
            "party": member["party"],
            "file": filename
        })
    
    index_data["state_constituencies"][state] = {
        "count": state_data["count"],
        "members": members_with_files
    }

# Update notes
index_data["notes"] = "Complete database of all 360 House of Representatives members for the 10th National Assembly (2023-2027)."

# Write updated index
with open(base_dir / "_index.json", "w") as f:
    json.dump(index_data, f, indent=2)

print("Index updated!")

# Count total members
total = 0
for state, data in index_data["state_constituencies"].items():
    total += data["count"]
print(f"\nTotal members in index: {total}")
