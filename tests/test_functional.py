from src.models import Bill, Parameters, TenantBlacklistEntry, TenantSettlement, ApartmentSettlement, Transfer
from src.manager import Manager


def test_settlement_due_between_tanants_and_apartment():
    manager = Manager(Parameters())

    settlement: ApartmentSettlement = manager.get_settlement('apart-polanka', 2025, 1)
    
    tenants_settlements: list[TenantSettlement] = manager.create_tenants_settlements(settlement)
    assert len(tenants_settlements) == 3

    total_due = sum([tenant_settlement.total_due_pln for tenant_settlement in tenants_settlements])
    assert total_due == settlement.total_due_pln

def test_debtors_calculation():
    manager = Manager(Parameters())

    debtors = manager.get_debtors('apart-polanka', 2025, 1)
    assert len(debtors) == 0

    debtors = manager.get_debtors('apart-polanka', 2025, 2)
    assert len(debtors) == 3


def test_tax_calculation():
    manager = Manager(Parameters())
    
    tax = manager.calculate_tax(2025, 1, 0.085)
    assert tax == 638 # 0.085 * 7500.0

    tax = manager.calculate_tax(2025, 2, 0.085)
    assert tax == 0

def test_deposits_calculation():
    manager = Manager(Parameters())
    
    deposit_balance = manager.check_deposits()
    assert deposit_balance == -8700.0 # no deposit in transfers

    manager.transfers.append(Transfer(
        tenant='tenant-1',
        date='2025-01-01',
        settlement_year=None,
        settlement_month=None,
        amount_pln=1000.0,
        type='deposit'
    ))

    deposit_balance = manager.check_deposits()
    assert deposit_balance == -7700.0 # 1000.0 deposit in transfers

def test_annual_balance_calculation():
    manager = Manager(Parameters())
    
    annual_balance = manager.get_annual_balance(2025)
    assert annual_balance == 6490.0 # 7500.0 in transfers minus 910.0 in bills

    manager.bills.append(Bill(
        apartment='apart-polanka',
        date_due='2025-02-15',
        settlement_year=2025,
        settlement_month=5,
        amount_pln=500.0,
        type='rent'
    ))

    manager.bills.append(Bill(
        apartment='apart-polanka',
        date_due='2025-02-15',
        settlement_year=2025,
        settlement_month=5,
        amount_pln=4500.0,
        type='renovation'
    ))

    annual_balance = manager.get_annual_balance(2025)
    assert annual_balance == 1490.0 # 7500.0 in transfers minus 910.0 in bills minus new bills 500.0 and 4500.0

def test_apartment_has_any_bills():
    manager = Manager(Parameters())
    
    has_bills = manager.has_any_bills('apart-polanka', 2025, 1)
    assert has_bills == True

    has_bills = manager.has_any_bills('apart-polanka', 2025, 3)
    assert has_bills == False

def test_min_max_transfer_amount():
    manager = Manager(Parameters())

    success = manager.check_transfers_amount_range()
    assert success == True

    manager.transfers[-1].amount_pln = 10000
    success = manager.check_transfers_amount_range()
    assert success == False

    manager.transfers[-1].amount_pln = -3000
    success = manager.check_transfers_amount_range()
    assert success == False

def test_tenant_blacklist_check():
    manager = Manager(Parameters())

    is_blacklisted = manager.check_tenant_blacklist('Jan Pawlak')
    assert is_blacklisted == False

    manager.tenants_blacklist.append(TenantBlacklistEntry(
        tenant='Jan Pawlak',
        reason='Previous unpaid rent'
    ))

    is_blacklisted = manager.check_tenant_blacklist('Jan Pawlak')
    assert is_blacklisted == True

def test_transfer_valid_with_tenant_agreement():
    manager = Manager(Parameters())

    is_valid = manager.check_transfers_tenant()
    assert is_valid == True

    manager.transfers.append(Transfer(
        tenant='non-existing-tenant',
        date='2025-01-01',
        settlement_year=2025,
        settlement_month=1,
        amount_pln=1000.0,
        type='rent'
    ))

    is_valid = manager.check_transfers_tenant()
    assert is_valid == False

    manager.transfers.pop()
    manager.transfers.append(Transfer(
        tenant='tenant-1',
        date='2025-01-01',
        settlement_year=1999,
        settlement_month=1,
        amount_pln=1000.0,
        type='rent'
    ))

    is_valid = manager.check_transfers_tenant()
    assert is_valid == False

import pytest

from src.manager import Manager
from src.models import ApartmentEvent, Parameters


def test_load_additional_data_reads_apartment_events():
    parameters = Parameters()
    manager = Manager(parameters)

    assert manager.apartment_events == []

    manager.load_additional_data()

    assert isinstance(manager.apartment_events, list)
    assert len(manager.apartment_events) == 3
    assert all(isinstance(event, ApartmentEvent) for event in manager.apartment_events)
    assert all(event.apartment == 'apart-polanka' for event in manager.apartment_events)


def test_generate_apartment_events_report_only_unsolved_by_default():
    manager = Manager(Parameters())
    manager.apartment_events = [
        ApartmentEvent(date='2024-06-01', apartment='apart-polanka', description='Fix light', solved=False),
        ApartmentEvent(date='2024-06-02', apartment='apart-polanka', description='Replace lock', solved=True),
        ApartmentEvent(date='2024-06-03', apartment='apart-other', description='Check wiring', solved=False),
    ]

    report = manager.generate_apartment_events_report('apart-polanka')

    assert len(report) == 1
    assert report[0].description == 'Fix light'
    assert report[0].solved is False


def test_generate_apartment_events_report_returns_all_when_only_unsolved_false():
    manager = Manager(Parameters())
    manager.apartment_events = [
        ApartmentEvent(date='2024-06-01', apartment='apart-polanka', description='Fix light', solved=False),
        ApartmentEvent(date='2024-06-02', apartment='apart-polanka', description='Replace lock', solved=True),
    ]

    report = manager.generate_apartment_events_report('apart-polanka', only_unsolved=False)

    assert len(report) == 2
    assert {event.solved for event in report} == {False, True}


def test_generate_apartment_events_report_raises_for_unknown_apartment():
    manager = Manager(Parameters())

    with pytest.raises(ValueError, match='Apartment key does not exist'):
        manager.generate_apartment_events_report('invalid-apartment')