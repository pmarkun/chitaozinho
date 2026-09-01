path "sys/health" {
  capabilities = ["read"]
}

path "sys/seal-status" {
  capabilities = ["read"]
}

path "sys/mounts" {
  capabilities = ["read"]
}

path "sys/mounts/transit" {
  capabilities = ["create", "read", "update", "delete", "sudo"]
}

path "sys/auth" {
  capabilities = ["read"]
}

path "sys/auth/approle" {
  capabilities = ["create", "read", "update", "delete", "sudo"]
}

path "sys/auth/userpass" {
  capabilities = ["create", "read", "update", "delete", "sudo"]
}

path "sys/policies/acl/chitaozinho-*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

path "auth/approle/role/chitaozinho-*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

path "auth/approle/role/chitaozinho-*/role-id" {
  capabilities = ["read"]
}

path "auth/approle/role/chitaozinho-*/secret-id" {
  capabilities = ["create", "update"]
}

path "auth/userpass/users/chitaozinho-operator" {
  capabilities = ["create", "read", "update", "delete"]
}

path "transit/keys/chitaozinho-server" {
  capabilities = ["create", "read", "update"]
}

path "transit/keys/chitaozinho-server/rotate" {
  capabilities = ["update"]
}
