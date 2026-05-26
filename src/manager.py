from datetime import datetime
from typing import List
from src.models import Apartment, Bill, Parameters, Tenant, ApartmentEvent, TenantBlacklistEntry, TenantSettlement, Transfer, ApartmentSettlement

class Manager:
    def __init__(self, parameters: Parameters):
        self.parameters = parameters

        self.apartments = {}
        self.tenants = {}
        self.transfers = []
        self.bills = []
        self.tenants_blacklist = []
        self.apartment_events = []
        self.load_data()

    def load_data(self):
        self.apartments = Apartment.from_json_file(self.parameters.apartments_json_path)
        self.tenants = Tenant.from_json_file(self.parameters.tenants_json_path)
        self.transfers = Transfer.from_json_file(self.parameters.transfers_json_path)
        self.bills = Bill.from_json_file(self.parameters.bills_json_path)
        self.tenants_blacklist = TenantBlacklistEntry.from_json_file(self.parameters.tenants_blacklist_json_path)

    def load_additional_data(self):
        self.apartment_events = ApartmentEvent.from_json_file(self.parameters.apartment_events_json_path)

    def generate_apartment_events_report(self, apartment_key: str, only_unsolved: bool = True) -> List[ApartmentEvent]:
        if apartment_key not in self.apartments:
            raise ValueError("Apartment key does not exist")
        return [
            event for event in self.apartment_events
            if event.apartment == apartment_key and(not event.solved or not only_unsolved)
        ]

    def check_tenants_apartment_keys(self) -> bool:
        for tenant in self.tenants.values():
            if tenant.apartment not in self.apartments:
                return False
        return True

    def get_apartment(self, apartment_key: str) -> Apartment | None:
        return self.apartments.get(apartment_key, None)

    def get_apartment_costs(self, apartment_key: str, year: int = None, month: int = None) -> float | None:
        if month is not None and (month < 1 or month > 12):
            raise ValueError("Month must be between 1 and 12")
        if apartment_key not in self.apartments:
            return None
        total_cost = 0.0
        for bill in self.bills:
            if bill.apartment == apartment_key and (year is None or bill.settlement_year == year) and (month is None or bill.settlement_month == month):
                total_cost += bill.amount_pln
        return total_cost

    def get_settlement(self, apartment_key: str, year: int, month: int) -> ApartmentSettlement | None:
        if month < 1 or month > 12:
            raise ValueError("Month must be between 1 and 12")
        if apartment_key not in self.apartments:
            return None
        total_cost = self.get_apartment_costs(apartment_key, year, month)
        if total_cost is None:
            return None
        return ApartmentSettlement(
            key=f"{apartment_key}-{year}-{month}",
            apartment=apartment_key,
            year=year,
            month=month,
            total_due_pln=total_cost
        )

    def create_tenants_settlements(self, apartment_settlement: ApartmentSettlement) -> List[TenantSettlement] | None:
        if apartment_settlement.month < 1 or apartment_settlement.month > 12:
            raise ValueError("Month must be between 1 and 12")
        if apartment_settlement.apartment not in self.apartments:
            return None
        tenants_in_apartment = [tenant for tenant in self.tenants.values() if tenant.apartment == apartment_settlement.apartment]
        if not tenants_in_apartment:
            return []

        return [
          TenantSettlement(
            tenant=tenant.name,
            apartment_settlement=apartment_settlement.key,
            month=apartment_settlement.month,
            year=apartment_settlement.year,
            total_due_pln=apartment_settlement.total_due_pln / len(tenants_in_apartment)
          ) for tenant in tenants_in_apartment]

    def get_debtors(self, apartment_key: str, year: int, month: int) -> List[str]:
        if month < 1 or month > 12:
            raise ValueError("Month must be between 1 and 12")
        output = []
        settlement = self.get_settlement(apartment_key, year, month)
        tenant_settlements = self.create_tenants_settlements(settlement)

        for tenant_settlement in tenant_settlements:
            tenant_transfers = [transfer for transfer in self.transfers if self.tenants[transfer.tenant].name == tenant_settlement.tenant and transfer.settlement_year == year and transfer.settlement_month == month]
            total_paid = sum(transfer.amount_pln for transfer in tenant_transfers if transfer.settlement_year == year and transfer.settlement_month == month)
            if total_paid < tenant_settlement.total_due_pln:
                output.append(tenant_settlement.tenant)
        return output

    def calculate_tax(self, year: int, month: int, tax_rate: float) -> float:
        total_income = sum(transfer.amount_pln for transfer in self.transfers if transfer.settlement_year == year and transfer.settlement_month == month)
        return round(total_income * tax_rate, 0)

    def check_deposits(self) -> float:
        total_deposits = 0.0
        total_due = 0.0
        for tenant in self.tenants.values():
            total_deposits += sum(transfer.amount_pln for transfer in self.transfers if self.tenants[transfer.tenant].name == tenant.name and transfer.type == 'deposit')
            total_due += tenant.deposit_pln

        return total_deposits - total_due

    def get_annual_balance(self, year: int) -> float:
        total_income = sum(transfer.amount_pln for transfer in self.transfers if transfer.settlement_year == year)
        total_due = sum(bill.amount_pln for bill in self.bills if bill.settlement_year == year)
        return total_income - total_due

    def has_any_bills(self, apartment_key: str, year: int, month: int) -> bool:
        if month < 1 or month > 12:
            raise ValueError("Month must be between 1 and 12")
        if apartment_key not in self.apartments:
            raise ValueError("Apartment key does not exist")
        return any(bill for bill in self.bills if bill.apartment == apartment_key and bill.settlement_year == year and bill.settlement_month == month)

    def check_transfers_amount_range(self) -> bool:
        for transfer in self.transfers:
            if transfer.amount_pln > self.parameters.max_transfer_pln or transfer.amount_pln < -self.parameters.max_refund_pln:
                return False
        return True

    def check_tenant_blacklist(self, tenant_name: str) -> bool:
        return any(entry for entry in self.tenants_blacklist if entry.tenant == tenant_name)

    def check_transfers_tenant(self) -> bool:
        for transfer in self.transfers:
            if transfer.tenant not in self.tenants:
                return False
            if transfer.settlement_year is not None and transfer.settlement_month is not None:
                agreement_from = self.tenants[transfer.tenant].date_agreement_from
                agreement_from = datetime.strptime(agreement_from, "%Y-%m-%d").date()
                agreement_to = self.tenants[transfer.tenant].date_agreement_to
                agreement_to = datetime.strptime(agreement_to, "%Y-%m-%d").date()
                if (transfer.settlement_year < agreement_from.year) or (transfer.settlement_year > agreement_to.year):
                    return False

        return True
    