import pytest

from app.services import booking

# 2026-11-23 is a Monday (09:00–17:00); 2026-11-22 is a Sunday (closed).
MONDAY = "2026-11-23"
SUNDAY = "2026-11-22"


def test_availability_on_open_day(temp_db):
    slots = booking.check_availability(MONDAY, "cleaning")
    assert slots[0] == "09:00"
    # 60-minute service: last slot must end by 17:00
    assert slots[-1] == "16:00"
    assert "16:30" not in slots


def test_availability_closed_day_is_empty(temp_db):
    assert booking.check_availability(SUNDAY, "cleaning") == []


def test_availability_unknown_service(temp_db):
    with pytest.raises(booking.BookingError):
        booking.check_availability(MONDAY, "haircut")


def test_book_removes_slot_and_overlaps(temp_db):
    appt = booking.book_appointment("cleaning", MONDAY, "10:00", "Alice", "555-0001")
    assert appt["status"] == "booked"
    slots = booking.check_availability(MONDAY, "cleaning")
    # The booked hour and any start that would overlap it are gone
    assert "10:00" not in slots
    assert "10:30" not in slots
    assert "09:30" not in slots  # 60-min service starting 09:30 overlaps 10:00
    assert "09:00" in slots
    assert "11:00" in slots


def test_double_book_rejected(temp_db):
    booking.book_appointment("cleaning", MONDAY, "10:00", "Alice", "555-0001")
    with pytest.raises(booking.BookingError):
        booking.book_appointment("cleaning", MONDAY, "10:00", "Bob", "555-0002")


def test_book_requires_name_and_phone(temp_db):
    with pytest.raises(booking.BookingError):
        booking.book_appointment("cleaning", MONDAY, "10:00", "  ", "555-0001")


def test_find_appointments_by_phone(temp_db):
    booking.book_appointment("cleaning", MONDAY, "10:00", "Alice", "555-0001")
    booking.book_appointment("consultation", MONDAY, "14:00", "Alice", "555-0001")
    found = booking.find_appointments("555-0001")
    assert len(found) == 2
    assert booking.find_appointments("555-9999") == []


def test_cancel_frees_slot(temp_db):
    appt = booking.book_appointment("cleaning", MONDAY, "10:00", "Alice", "555-0001")
    cancelled = booking.cancel_appointment(appt["id"])
    assert cancelled["status"] == "cancelled"
    assert "10:00" in booking.check_availability(MONDAY, "cleaning")
    with pytest.raises(booking.BookingError):
        booking.cancel_appointment(appt["id"])  # already cancelled


def test_reschedule_moves_appointment(temp_db):
    appt = booking.book_appointment("cleaning", MONDAY, "10:00", "Alice", "555-0001")
    moved = booking.reschedule_appointment(appt["id"], MONDAY, "13:00")
    assert moved["time"] == "13:00"
    assert moved["status"] == "booked"
    slots = booking.check_availability(MONDAY, "cleaning")
    assert "10:00" in slots  # old slot freed
    assert "13:00" not in slots
    assert booking.get_appointment(appt["id"])["status"] == "cancelled"


def test_reschedule_to_taken_slot_keeps_original(temp_db):
    a = booking.book_appointment("cleaning", MONDAY, "10:00", "Alice", "555-0001")
    booking.book_appointment("cleaning", MONDAY, "13:00", "Bob", "555-0002")
    with pytest.raises(booking.BookingError):
        booking.reschedule_appointment(a["id"], MONDAY, "13:00")
    assert booking.get_appointment(a["id"])["status"] == "booked"
