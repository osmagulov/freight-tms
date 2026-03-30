import logging
import re
import csv
import io
import pandas as pd
from typing import List, Dict, Any, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models import Expense, Trip, Driver, ExpenseType

logger = logging.getLogger(__name__)

class FuelAntifraudService:
    @staticmethod
    def parse_manual_csv(file_content: str) -> List[Dict[str, Any]]:
        """Parses the manual driver report CSV as provided in the user script."""
        try:
            # Use pandas as requested by user logic (skiprows=3)
            df_rep = pd.read_csv(io.StringIO(file_content), skiprows=3)
            manual_data = []
            
            for _, row in df_rep.iterrows():
                # Based on user script:
                # row.iloc[0]: Date
                # row.iloc[1]: Card (contains 2810558...)
                # row.iloc[2]: Liters
                # row.iloc[5]: Driver name
                
                try:
                    date_val = str(row.iloc[0]).strip()
                    card_raw = str(row.iloc[1]).strip().replace(' ', '').replace('.0', '')
                    
                    try:
                        liters_str = str(row.iloc[2]).replace(' ', '').replace(',', '.')
                        liters = float(liters_str)
                    except (ValueError, TypeError):
                        liters = 0.0
                        
                    driver = str(row.iloc[5]).strip()
                    
                    # Match card pattern 2810558XXXXX and take last 4 digits
                    match = re.search(r'2810558(\d{3,4})', card_raw)
                    if match and liters > 0 and driver != 'nan' and driver != 'None':
                        manual_data.append({
                            'date': date_val,
                            'card_last4': match.group(1)[-4:],
                            'driver': driver,
                            'liters': liters
                        })
                except Exception as e:
                    logger.debug(f"Skipping row due to: {e}")
                    continue
            return manual_data
        except Exception as e:
            logger.error(f"Error parsing manual CSV: {e}")
            return []

    @staticmethod
    def parse_station_transactions(file_content: str) -> List[Dict[str, Any]]:
        """Parses the gas station transactions CSV as provided in the user script."""
        trans_data = []
        try:
            reader = csv.reader(io.StringIO(file_content))
            current_card = None
            for row in reader:
                if not row:
                    continue
                
                # Based on user script:
                # Header row: ["Номер карты", "2810558XXXX", ...]
                if len(row) > 1 and row[0].strip() == 'Номер карты':
                    match = re.search(r'2810558(\d{3,4})', row[1].strip())
                    if match:
                        current_card = match.group(1)[-4:]
                
                # Transaction row: [Date, ..., Column 13: Liters]
                elif len(row) >= 14 and current_card:
                    date_str = row[0].strip()
                    # User's heuristic for date: "DD.MM.YYYY"
                    if len(date_str) == 10 and date_str[2] == '.' and date_str[5] == '.':
                        try:
                            amount = float(row[13].strip().replace(',', '.'))
                            trans_data.append({
                                'date': date_str,
                                'card_last4': current_card,
                                'liters': amount
                            })
                        except (ValueError, TypeError):
                            pass
            return trans_data
        except Exception as e:
            logger.error(f"Error parsing transaction CSV: {e}")
            return []

    @classmethod
    async def get_manual_data_from_db(cls, session: AsyncSession) -> List[Dict[str, Any]]:
        """Fetches manual fuel reports directly from the database Expenses table."""
        stmt = (
            select(Expense, Driver)
            .join(Trip, Expense.trip_id == Trip.id)
            .join(Driver, Trip.driver_id == Driver.id)
            .where(Expense.expense_type == ExpenseType.FUEL.value)
        )
        result = await session.execute(stmt)
        
        manual_data = []
        for expense, driver in result.all():
            if not expense.liters:
                continue
                
            # Use driver's fuel card if available
            card_last4 = None
            if driver.fuel_card_number:
                # Try to extract last 4 digits if it's the full number
                match = re.search(r'2810558(\d{3,4})', driver.fuel_card_number.replace(' ', ''))
                if match:
                    card_last4 = match.group(1)[-4:]
                else:
                    # If it's just some digits, take last 4
                    digits = re.sub(r'\D', '', driver.fuel_card_number)
                    if len(digits) >= 4:
                        card_last4 = digits[-4:]
            
            manual_data.append({
                'date': expense.created_at.strftime("%d.%m.%Y"),
                'card_last4': card_last4 or "Unknown",
                'driver': driver.name or f"Driver ID:{driver.id}",
                'liters': expense.liters,
                'expense_id': expense.id
            })
        return manual_data

    @classmethod
    def check_fraud(cls, manual_data: List[Dict[str, Any]], trans_data: List[Dict[str, Any]]) -> List[str]:
        """Runs the antifraud logic on provided data sets."""
        red_flags = []
        
        # 1. Separating valid transactions and returns
        valid_trans = [t for t in trans_data if t['liters'] > 0]
        returns = [t for t in trans_data if t['liters'] < 0]
        
        # Scheme A: Return reported as purchase
        for ret in returns:
            abs_liters = abs(ret['liters'])
            for man in manual_data:
                if man['card_last4'] == ret['card_last4'] and abs(man['liters'] - abs_liters) < 0.01:
                    red_flags.append(
                        f"🚨 ВОЗВРАТ КАК ЗАПРАВКА: Водитель {man['driver']} (карта ...{man['card_last4']}) "
                        f"сдал чек на {man['liters']} л. В базе это ВОЗВРАТ!"
                    )

        # Scheme B: Phantom receipts
        # To avoid N^2, let's group trans by card
        trans_by_card = {}
        for t in valid_trans:
            card = t['card_last4']
            if card not in trans_by_card:
                trans_by_card[card] = []
            trans_by_card[card].append(t)
            
        returns_by_card = {}
        for r in returns:
            card = r['card_last4']
            if card not in returns_by_card:
                returns_by_card[card] = []
            returns_by_card[card].append(r)

        for man in manual_data:
            card = man['card_last4']
            liters = man['liters']
            
            # Check if exists in valid transactions
            found_exact = False
            if card in trans_by_card:
                for t in trans_by_card[card]:
                    if abs(t['liters'] - liters) < 0.01:
                        found_exact = True
                        break
            
            # Check if it was a return (handled in Scheme A, but check here to avoid phantom flag)
            found_return = False
            if card in returns_by_card:
                for r in returns_by_card[card]:
                    if abs(abs(r['liters']) - liters) < 0.01:
                        found_return = True
                        break
            
            if not found_exact and not found_return:
                # In user's script, there was a date filter: '2026-03' in str(man['Дата'])
                # We can make it optional or keep it as a broad heuristic
                red_flags.append(
                    f"👻 ФАНТОМНЫЙ ЧЕК: Водитель {man['driver']} (карта ...{card}) "
                    f"отчитался за {liters} л от {man['date']}. В базе АЗС такой заправки НЕ СУЩЕСТВУЕТ!"
                )
                
        return list(set(red_flags)) # Return unique flags
