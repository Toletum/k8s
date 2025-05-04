# pip install scylla-driver 

from time import sleep

from cassandra.cluster import Cluster
from cassandra import OperationTimedOut
from cassandra.policies import HostStateListener

scylla_hosts = ['192.168.122.200', '192.168.122.201', '192.168.122.202']


try:
    cluster = Cluster(scylla_hosts)
    session = cluster.connect()
    print("Conexión exitosa a ScyllaDB")
except OperationTimedOut:
    print("Tiempo de espera agotado. Verifica los nodos.")
except Exception as e:
    print(f"Error al conectar: {e}")
    exit(1)

keyspace = 'my_keyspace'
try:
    session.set_keyspace(keyspace)
except Exception as e:
    print(f"Error al establecer el keyspace: {e}")
    exit(1)

try:
    while True:
      for host in cluster.metadata.all_hosts():
        print(f"- {host.address}: {'Activo' if host.is_up else 'Inactivo'}")

      result = session.execute('SELECT * FROM users')
      for row in result:
          print(row)
      sleep(0.1)
except Exception as e:
    print(f"Error al ejecutar la consulta: {e}")
