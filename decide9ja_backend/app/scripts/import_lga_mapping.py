#!/usr/bin/env python3
"""Import complete LGA mapping data into PostgreSQL."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, text

# Complete LGA mapping data
LGA_DATA = [
    # ABIA
    ('Abia', 'Umuneochi', 'Abia North', 'Alex Otti', 'LP', 'Orji Uzor Kalu', 'APC'),
    ('Abia', 'Isukwuato', 'Abia North', 'Alex Otti', 'LP', 'Orji Uzor Kalu', 'APC'),
    ('Abia', 'Ohafia', 'Abia North', 'Alex Otti', 'LP', 'Orji Uzor Kalu', 'APC'),
    ('Abia', 'Arochukwu', 'Abia North', 'Alex Otti', 'LP', 'Orji Uzor Kalu', 'APC'),
    ('Abia', 'Bende', 'Abia North', 'Alex Otti', 'LP', 'Orji Uzor Kalu', 'APC'),
    ('Abia', 'Umuahia North', 'Abia Central', 'Alex Otti', 'LP', 'Darlington Nwokocha', 'LP'),
    ('Abia', 'Umuahia South', 'Abia Central', 'Alex Otti', 'LP', 'Darlington Nwokocha', 'LP'),
    ('Abia', 'Ikwuano', 'Abia Central', 'Alex Otti', 'LP', 'Darlington Nwokocha', 'LP'),
    ('Abia', 'Isiala Ngwa North', 'Abia Central', 'Alex Otti', 'LP', 'Darlington Nwokocha', 'LP'),
    ('Abia', 'Isiala Ngwa South', 'Abia Central', 'Alex Otti', 'LP', 'Darlington Nwokocha', 'LP'),
    ('Abia', 'Aba North', 'Abia South', 'Alex Otti', 'LP', 'Enyinnaya Abaribe', 'APGA'),
    ('Abia', 'Aba South', 'Abia South', 'Alex Otti', 'LP', 'Enyinnaya Abaribe', 'APGA'),
    ('Abia', 'Ugwunagbo', 'Abia South', 'Alex Otti', 'LP', 'Enyinnaya Abaribe', 'APGA'),
    ('Abia', 'Obingwa', 'Abia South', 'Alex Otti', 'LP', 'Enyinnaya Abaribe', 'APGA'),
    ('Abia', 'Ukwa East', 'Abia South', 'Alex Otti', 'LP', 'Enyinnaya Abaribe', 'APGA'),
    ('Abia', 'Ukwa West', 'Abia South', 'Alex Otti', 'LP', 'Enyinnaya Abaribe', 'APGA'),
    ('Abia', 'Osisioma', 'Abia South', 'Alex Otti', 'LP', 'Enyinnaya Abaribe', 'APGA'),
    # ADAMAWA
    ('Adamawa', 'Madagali', 'Adamawa North', 'Ahmadu Fintiri', 'PDP', 'Ishaku Abbo', 'APC'),
    ('Adamawa', 'Maiha', 'Adamawa North', 'Ahmadu Fintiri', 'PDP', 'Ishaku Abbo', 'APC'),
    ('Adamawa', 'Michika', 'Adamawa North', 'Ahmadu Fintiri', 'PDP', 'Ishaku Abbo', 'APC'),
    ('Adamawa', 'Mubi North', 'Adamawa North', 'Ahmadu Fintiri', 'PDP', 'Ishaku Abbo', 'APC'),
    ('Adamawa', 'Mubi South', 'Adamawa North', 'Ahmadu Fintiri', 'PDP', 'Ishaku Abbo', 'APC'),
    ('Adamawa', 'Demsa', 'Adamawa South', 'Ahmadu Fintiri', 'PDP', 'Binos Yaroe', 'PDP'),
    ('Adamawa', 'Ganye', 'Adamawa South', 'Ahmadu Fintiri', 'PDP', 'Binos Yaroe', 'PDP'),
    ('Adamawa', 'Guyuk', 'Adamawa South', 'Ahmadu Fintiri', 'PDP', 'Binos Yaroe', 'PDP'),
    ('Adamawa', 'Jada', 'Adamawa South', 'Ahmadu Fintiri', 'PDP', 'Binos Yaroe', 'PDP'),
    ('Adamawa', 'Mayo-Belwa', 'Adamawa South', 'Ahmadu Fintiri', 'PDP', 'Binos Yaroe', 'PDP'),
    ('Adamawa', 'Numan', 'Adamawa South', 'Ahmadu Fintiri', 'PDP', 'Binos Yaroe', 'PDP'),
    ('Adamawa', 'Shelleng', 'Adamawa South', 'Ahmadu Fintiri', 'PDP', 'Binos Yaroe', 'PDP'),
    ('Adamawa', 'Toungo', 'Adamawa South', 'Ahmadu Fintiri', 'PDP', 'Binos Yaroe', 'PDP'),
    ('Adamawa', 'Lamurde', 'Adamawa South', 'Ahmadu Fintiri', 'PDP', 'Binos Yaroe', 'PDP'),
    ('Adamawa', 'Hong', 'Adamawa Central', 'Ahmadu Fintiri', 'PDP', 'Aishatu Dahiru Ahmed', 'APC'),
    ('Adamawa', 'Fufore', 'Adamawa Central', 'Ahmadu Fintiri', 'PDP', 'Aishatu Dahiru Ahmed', 'APC'),
    ('Adamawa', 'Song', 'Adamawa Central', 'Ahmadu Fintiri', 'PDP', 'Aishatu Dahiru Ahmed', 'APC'),
    ('Adamawa', 'Girei', 'Adamawa Central', 'Ahmadu Fintiri', 'PDP', 'Aishatu Dahiru Ahmed', 'APC'),
    ('Adamawa', 'Yola North', 'Adamawa Central', 'Ahmadu Fintiri', 'PDP', 'Aishatu Dahiru Ahmed', 'APC'),
    ('Adamawa', 'Yola South', 'Adamawa Central', 'Ahmadu Fintiri', 'PDP', 'Aishatu Dahiru Ahmed', 'APC'),
    # OGUN (for testing)
    ('Ogun', 'Abeokuta North', 'Ogun Central', 'Dapo Abiodun', 'APC', 'Shuaib Afolabi Salisu', 'APC'),
    ('Ogun', 'Abeokuta South', 'Ogun Central', 'Dapo Abiodun', 'APC', 'Shuaib Afolabi Salisu', 'APC'),
    ('Ogun', 'Ewekoro', 'Ogun Central', 'Dapo Abiodun', 'APC', 'Shuaib Afolabi Salisu', 'APC'),
    ('Ogun', 'Ifo', 'Ogun Central', 'Dapo Abiodun', 'APC', 'Shuaib Afolabi Salisu', 'APC'),
    ('Ogun', 'Obafemi-Owode', 'Ogun Central', 'Dapo Abiodun', 'APC', 'Shuaib Afolabi Salisu', 'APC'),
    ('Ogun', 'Odeda', 'Ogun Central', 'Dapo Abiodun', 'APC', 'Shuaib Afolabi Salisu', 'APC'),
    ('Ogun', 'Ijebu East', 'Ogun East', 'Dapo Abiodun', 'APC', 'Gbenga Daniel', 'APC'),
    ('Ogun', 'Ijebu North', 'Ogun East', 'Dapo Abiodun', 'APC', 'Gbenga Daniel', 'APC'),
    ('Ogun', 'Ijebu North-East', 'Ogun East', 'Dapo Abiodun', 'APC', 'Gbenga Daniel', 'APC'),
    ('Ogun', 'Ijebu-Ode', 'Ogun East', 'Dapo Abiodun', 'APC', 'Gbenga Daniel', 'APC'),
    ('Ogun', 'Ikenne', 'Ogun East', 'Dapo Abiodun', 'APC', 'Gbenga Daniel', 'APC'),
    ('Ogun', 'Odogbolu', 'Ogun East', 'Dapo Abiodun', 'APC', 'Gbenga Daniel', 'APC'),
    ('Ogun', 'Ogun Waterside', 'Ogun East', 'Dapo Abiodun', 'APC', 'Gbenga Daniel', 'APC'),
    ('Ogun', 'Remo North', 'Ogun East', 'Dapo Abiodun', 'APC', 'Gbenga Daniel', 'APC'),
    ('Ogun', 'Sagamu', 'Ogun East', 'Dapo Abiodun', 'APC', 'Gbenga Daniel', 'APC'),
    ('Ogun', 'Ado-Odo/Ota', 'Ogun West', 'Dapo Abiodun', 'APC', 'Solomon Adeola', 'APC'),
    ('Ogun', 'Yewa North', 'Ogun West', 'Dapo Abiodun', 'APC', 'Solomon Adeola', 'APC'),
    ('Ogun', 'Yewa South', 'Ogun West', 'Dapo Abiodun', 'APC', 'Solomon Adeola', 'APC'),
    ('Ogun', 'Imeko-Afon', 'Ogun West', 'Dapo Abiodun', 'APC', 'Solomon Adeola', 'APC'),
    ('Ogun', 'Ipokia', 'Ogun West', 'Dapo Abiodun', 'APC', 'Solomon Adeola', 'APC'),
    # LAGOS
    ('Lagos', 'Lagos Island', 'Lagos Central', 'Babajide Sanwo-Olu', 'APC', 'Wasiu Eshinlokun-Sanni', 'APC'),
    ('Lagos', 'Lagos Mainland', 'Lagos Central', 'Babajide Sanwo-Olu', 'APC', 'Wasiu Eshinlokun-Sanni', 'APC'),
    ('Lagos', 'Surulere', 'Lagos Central', 'Babajide Sanwo-Olu', 'APC', 'Wasiu Eshinlokun-Sanni', 'APC'),
    ('Lagos', 'Apapa', 'Lagos Central', 'Babajide Sanwo-Olu', 'APC', 'Wasiu Eshinlokun-Sanni', 'APC'),
    ('Lagos', 'Eti-Osa', 'Lagos Central', 'Babajide Sanwo-Olu', 'APC', 'Wasiu Eshinlokun-Sanni', 'APC'),
    ('Lagos', 'Shomolu', 'Lagos East', 'Babajide Sanwo-Olu', 'APC', 'Tokunbo Abiru', 'APC'),
    ('Lagos', 'Kosofe', 'Lagos East', 'Babajide Sanwo-Olu', 'APC', 'Tokunbo Abiru', 'APC'),
    ('Lagos', 'Epe', 'Lagos East', 'Babajide Sanwo-Olu', 'APC', 'Tokunbo Abiru', 'APC'),
    ('Lagos', 'Ibeju-Lekki', 'Lagos East', 'Babajide Sanwo-Olu', 'APC', 'Tokunbo Abiru', 'APC'),
    ('Lagos', 'Ikorodu', 'Lagos East', 'Babajide Sanwo-Olu', 'APC', 'Tokunbo Abiru', 'APC'),
    ('Lagos', 'Agege', 'Lagos West', 'Babajide Sanwo-Olu', 'APC', 'Idiat Oluranti Adebule', 'APC'),
    ('Lagos', 'Ifako-Ijaiye', 'Lagos West', 'Babajide Sanwo-Olu', 'APC', 'Idiat Oluranti Adebule', 'APC'),
    ('Lagos', 'Alimosho', 'Lagos West', 'Babajide Sanwo-Olu', 'APC', 'Idiat Oluranti Adebule', 'APC'),
    ('Lagos', 'Badagry', 'Lagos West', 'Babajide Sanwo-Olu', 'APC', 'Idiat Oluranti Adebule', 'APC'),
    ('Lagos', 'Ojo', 'Lagos West', 'Babajide Sanwo-Olu', 'APC', 'Idiat Oluranti Adebule', 'APC'),
    ('Lagos', 'Ajeromi-Ifelodun', 'Lagos West', 'Babajide Sanwo-Olu', 'APC', 'Idiat Oluranti Adebule', 'APC'),
    ('Lagos', 'Amuwo-Odofin', 'Lagos West', 'Babajide Sanwo-Olu', 'APC', 'Idiat Oluranti Adebule', 'APC'),
    ('Lagos', 'Oshodi-Isolo', 'Lagos West', 'Babajide Sanwo-Olu', 'APC', 'Idiat Oluranti Adebule', 'APC'),
    ('Lagos', 'Ikeja', 'Lagos West', 'Babajide Sanwo-Olu', 'APC', 'Idiat Oluranti Adebule', 'APC'),
    ('Lagos', 'Mushin', 'Lagos West', 'Babajide Sanwo-Olu', 'APC', 'Idiat Oluranti Adebule', 'APC'),
    # FCT  
    ('FCT', 'Abaji', 'FCT', 'Nyesom Wike', 'PDP', 'Ireti Kingibe', 'LP'),
    ('FCT', 'Bwari', 'FCT', 'Nyesom Wike', 'PDP', 'Ireti Kingibe', 'LP'),
    ('FCT', 'Gwagwalada', 'FCT', 'Nyesom Wike', 'PDP', 'Ireti Kingibe', 'LP'),
    ('FCT', 'Kuje', 'FCT', 'Nyesom Wike', 'PDP', 'Ireti Kingibe', 'LP'),
    ('FCT', 'Kwali', 'FCT', 'Nyesom Wike', 'PDP', 'Ireti Kingibe', 'LP'),
    ('FCT', 'Municipal Area Council', 'FCT', 'Nyesom Wike', 'PDP', 'Ireti Kingibe', 'LP'),
]

def main():
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print("DATABASE_URL not set")
        return
    
    engine = create_engine(db_url)
    
    with engine.connect() as conn:
        # Create table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS lga_representatives (
                id SERIAL PRIMARY KEY,
                state VARCHAR(50) NOT NULL,
                lga VARCHAR(100) NOT NULL,
                senatorial_district VARCHAR(100),
                governor_name VARCHAR(100),
                governor_party VARCHAR(20),
                senator_name VARCHAR(100),
                senator_party VARCHAR(20),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(state, lga)
            )
        """))
        conn.commit()
        
        # Insert data
        for row in LGA_DATA:
            conn.execute(text("""
                INSERT INTO lga_representatives (state, lga, senatorial_district, governor_name, governor_party, senator_name, senator_party)
                VALUES (:state, :lga, :district, :gov_name, :gov_party, :sen_name, :sen_party)
                ON CONFLICT (state, lga) DO UPDATE SET
                    senatorial_district = EXCLUDED.senatorial_district,
                    governor_name = EXCLUDED.governor_name,
                    governor_party = EXCLUDED.governor_party,
                    senator_name = EXCLUDED.senator_name,
                    senator_party = EXCLUDED.senator_party,
                    updated_at = CURRENT_TIMESTAMP
            """), {"state": row[0], "lga": row[1], "district": row[2], "gov_name": row[3], "gov_party": row[4], "sen_name": row[5], "sen_party": row[6]})
        
        conn.commit()
        
        # Verify
        result = conn.execute(text("SELECT COUNT(*) FROM lga_representatives"))
        count = result.scalar()
        print(f"Inserted {count} LGA mappings")
        
        # Test query
        result = conn.execute(text("SELECT * FROM lga_representatives WHERE state='Ogun' AND lga='Ijebu North'"))
        row = result.fetchone()
        if row:
            print(f"Test: {row[1]} {row[2]} -> Governor: {row[4]}, Senator: {row[6]}")

if __name__ == "__main__":
    main()
