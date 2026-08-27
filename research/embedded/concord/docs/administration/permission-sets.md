---
min_role: ADMIN
---
# Permission Sets

Permission sets control what each user can do in Concord. Every user is assigned exactly one set, and that set determines which pages they see, which actions they can take, and which API endpoints they can call.

## Built-in Sets

Concord ships with four built-in permission sets matching the role hierarchy:

| Set | Typical user | Scope |
|-----|-------------|-------|
| **Admin** | Platform owner | Everything -- user management, production deploys, system config |
| **Maintainer** | Platform engineer | Products, MTIBs, fixtures, staging. No user management |
| **Developer** | Firmware engineer | Builds, validation, test packages for assigned products |
| **Operator** | Factory technician | Manufacturing station -- scan devices, run POST, view results |

Built-in sets cannot be deleted or renamed. Their permissions are fixed.

## Custom Permission Sets

When the built-in sets don't fit -- say you need a role that can manage fixtures but not trigger builds -- create a custom set.

Open the **Users** page and switch to the **Permission Sets** tab. Click **New Set**.

The creation form has three fields:

- **Name** -- a label for the set (e.g., "QA Engineer")
- **Description** -- what this set is for
- **Permissions** -- checkboxes for every permission in the system. Check the ones this set should grant

Click **Create** and the set appears in the list immediately.

## Permission Count

Each set in the list shows a count badge formatted as `N/M` -- the number of granted permissions out of the total available. A set with `12/47` has 12 permissions enabled. This makes it easy to spot overly broad or overly narrow sets at a glance.

## Editing a Set

Click the **Edit** button on any custom set to modify it. You can change the description, add permissions, or remove them. Click **Save** when done. Changes take effect on the user's next API call -- there's no need to log out and back in.

## Assigning Sets to Users

Permission sets are assigned per-user through the Users page or the API. Open a user's profile, select the permission set from the dropdown, and save.

```bash
# Assign via API
curl -X PUT https://concord.local/v2/users/<user-id> \
  -H "Authorization: Bearer <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{"permissionSetId": "<set-id>"}'
```

## Deleting a Set

You cannot delete a permission set that has users assigned to it. The API returns a `409 Conflict` with a message indicating assigned users must be removed first.

To delete a custom set:

1. Reassign every user on that set to a different permission set (or set their `permissionSetId` to `null`)
2. Return to the Permission Sets tab
3. Click **Delete** on the set, then **Confirm** in the dialog

The set disappears from the list. Built-in sets are exempt from deletion entirely.

## Related

- [Users & Roles](users-and-roles.md) -- role hierarchy, product access levels, adding users
- [API Keys](api-keys.md) -- programmatic access tokens scoped to a user's permissions
