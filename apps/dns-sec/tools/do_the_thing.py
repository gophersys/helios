import dns.resolver
import dns.rdataclass
import dns.rdatatype
import dns.rrset
import dns.dnssec
import dns.rdtypes.ANY.DNSKEY
import base64

def get_ds_from_key(domain, key):
    # Extract key parameters
    flags, proto, alg, keydata_str = key.split(' ', 3)
    # Convert base64 string to bytes
    keydata = base64.b64decode(keydata_str)
    # Create a DNSKEY object
    dnskey_obj = dns.rdtypes.ANY.DNSKEY.DNSKEY(dns.rdatatype.DNSKEY, dns.rdataclass.IN, int(flags), int(proto), int(alg), keydata)
    # Construct RRset
    name_obj = dns.name.from_text(domain)
    key_rrset = dns.rrset.from_rdata_list(name_obj, 3600, [dnskey_obj])
    # Generate DS record
    return dns.dnssec.make_ds(name_obj, key_rrset, 'SHA256')

def validate_ds_with_dnskey(domain, ds_records, dnskey_records):
    for key in dnskey_records:
        if key.startswith("257"):  # Only considering KSKs
            generated_ds = get_ds_from_key(domain, key)
            for ds in ds_records:
                if ds.split()[3].upper() == generated_ds.to_text().split()[3].upper():
                    return True
    return False

if __name__ == '__main__':ldns-key2ds -2 dnskey_no_newline.txt
    domain = "mateosegura.com"
    
    # DS records provided
    ds_records = [
        "917 13 2 07BFDF94A9FCA92B89025033F7B0631148AD6C61D2401F032E6DACCF6968B4D5",
        "18720 13 2 2CB3B21759D909B9C5639C38BC734B1B3E7C819F53413FFA0443FD0E3739F2D5"
    ]

      # DNSKEY records provided
    dnskey_records = [
        "256 3 13 BkXc0DyoAyoRW6OtyGRJABOs7GttxWp3QhDbN/Y9ppp8gY4U13qsfLqUxCIN0SCBxpbpPWTYTL3oJ5YHA6psCw==",
        "256 3 13 5BqLSuE+AKxcMyaW3G9rEqXPmIzumOCQ03Oly7r6jO2DVokTAbR6CdT3O7Yx81jwJegbaRN+9cjRF+uv53s+NQ==",
        "257 3 13 YDyF5/XJ8wiEhwd7XFvjHDl8C3jVMZ6fV0CviCxtWlLfMHnvN8CIbefc1htM8w/fAhs1XSJsBLDfyBhsMFKpHQ==",
        "257 3 13 qH+9wrcq8WifJJpycZdem0TLQDTAC2hpHsD5aOLBVvRTH3HPrs4kYtT4eCScTJpAP+QtK76Rvu9pFLrzWD1k8g=="
    ]

      # Perform the validation
    is_valid = validate_ds_with_dnskey(domain, ds_records, dnskey_records)
    
    # Print the result
    if is_valid:
        print(f"The DS records for {domain} match one of the provided KSK DNSKEYs.")
    else:
        print(f"The DS records for {domain} do not match any of the provided KSK DNSKEYs.")