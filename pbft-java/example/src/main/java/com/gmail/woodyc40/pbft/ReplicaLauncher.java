package com.gmail.woodyc40.pbft;

import com.gmail.woodyc40.pbft.client.AdditionClient;
import com.gmail.woodyc40.pbft.client.AdditionClientEncoder;
import com.gmail.woodyc40.pbft.client.AdditionClientTransport;
//import com.gmail.woodyc40.pbft.metrics.AvailabilityMetrics;
import com.gmail.woodyc40.pbft.replica.AdditionReplica;
import com.gmail.woodyc40.pbft.replica.AdditionReplicaEncoder;
import com.gmail.woodyc40.pbft.replica.AdditionReplicaTransport;
import com.gmail.woodyc40.pbft.replica.NoopDigester;
import com.gmail.woodyc40.pbft.type.AdditionOperation;
import com.gmail.woodyc40.pbft.type.AdditionResult;
import redis.clients.jedis.Jedis;
import redis.clients.jedis.JedisPool;
import redis.clients.jedis.JedisPubSub;

import java.io.File;
import java.io.IOException;
import java.util.concurrent.CountDownLatch;

/**Parametric laucher for replicash and PBFT client
 * --client            => start the client
 * --replicaId=N       => id of the replica(0 ... N-1)
 * --tolerance=f       => number of tolerated Byzantine faults
 * --requests=K        => number of requests sent for the client
 * --interval=MS       => interval between two requests for the client
 * --timeout=MS        => timeout for pbft messages
 * --redis=HOST        => host del server Redis
 */
 

public class ReplicaLauncher {
    //private static final int TOLERANCE = 2;
    //private static final long TIMEOUT_MS = 1000;
    //private static final int REPLICA_COUNT = 3 * TOLERANCE + 1;

    public static void main(String[] args) throws InterruptedException, IOException {
        boolean isClient = false;
        //at the beginning replica id is -1 because is not set
        int replicaId = -1;
        int tolerance = 2;
        int numRequests = 1000000;
        long intervalMs = 1000;
        long timeoutMs = 1000;
        String redisHost = "192.168.1.189"; //name of container docker

        //cycling through the arguments to check if --client or a replica id is specified
        //if --client is specified it will run the client otherwise it will run the replica with the specified id
        for (String arg : args) {
            if (arg.equals("--client")) {
                isClient = true;
            } else if (arg.startsWith("--replicaId=")) {
                replicaId = Integer.parseInt(arg.substring("--replicaId=".length()));
            } else if (arg.startsWith("--tolerance=")) {
                tolerance = Integer.parseInt(arg.substring("--tolerance=".length()));
            } else if (arg.startsWith("--requests=")) {
                numRequests = Integer.parseInt(arg.substring("--requests=".length()));
            } else if (arg.startsWith("--interval=")) {
                intervalMs = Long.parseLong(arg.substring("--interval=".length()));
            } else if (arg.startsWith("--timeout=")) {
                timeoutMs = Long.parseLong(arg.substring("--timeout=".length()));
            } else if (arg.startsWith("--redis=")) {
                redisHost = arg.substring("--redis=".length());
            }
        }
        int replicaCount = 3 * tolerance + 1;

         //if neither --client nor --replicaId is spec, exit with error mex
        if (!isClient && replicaId == -1) {
            System.err.println("specificare --client oppure --replicaId=N");
            System.exit(1);
        }


        //cycling through the arguments to check if --redis is specified
        //in my case i set localhost 
        for (String arg : args) {
            if (arg.startsWith("--redis=")) {
                redisHost = arg.substring("--redis=".length());
            }
        }
        //create a pool of connections redis toward the host redisHost to the port 6379
        JedisPool pool = new JedisPool(redisHost, 6379);
        try{
                    if (isClient) {
                        runClient(pool, tolerance, timeoutMs, replicaCount, numRequests, intervalMs);
                    } else {
                        runReplica(replicaId, pool, tolerance, timeoutMs, replicaCount);
                    }
                    // keep the main thread alive to allow the client or replica to rum
                    synchronized (ReplicaLauncher.class) {
                        ReplicaLauncher.class.wait();
                        }
        } catch (InterruptedException e) {
                    System.out.println("applicazione interrotta");
        } finally {
                    pool.close();
                    System.out.println("pool Redis chiuso.");
                        }
                
            }
            

    //private static boolean isSafe = true;

    private static void runClient(JedisPool pool, int tolerance, long timeoutMs,
                                  int replicaCount, int numRequests, long intervalMs) {

        //to save the Log of the metrics
        File logDir = new File("/app/logs");
         if (!logDir.exists()) logDir.mkdir();

        //MISURAZIONE AVAILABILITY DAL LATO DEL CLIENT - COMMENTO PERCHE' ABBIAMO CAMBIATO METODO
        //for the availability metrics
        // AvailabilityMetrics metrics;
        //try {
        //    metrics = new AvailabilityMetrics("/app/logs/availability_metrics.log");
        //} catch (IOException e) {
        //    e.printStackTrace();
        //return;
        //}

        //create the client with the specified parameters and the transport and encoder to communicate with the replicas
        //the client will send requests to the replicas and receive responses
        //the client will use the AdditionClientEncoder to encode the requests and the AdditionClientTransport to send them
        AdditionClientEncoder encoder = new AdditionClientEncoder();
        //the transport will use Redis to communicate with the replicas and the jedis pool to get connections
        //the REPLICA_COUNT is the n of replicas that the client will commmunicate with
        AdditionClientTransport transport = new AdditionClientTransport(pool, replicaCount);

        //create the client
        AdditionClient client = new AdditionClient("client-0", tolerance, timeoutMs, encoder, transport);

        //to sincronize the start of the listener thread
        //the listener will listen for messages from the replicas and handle them
        //it will use the JedisPubSub to subscribe to the channel with the client id 
        CountDownLatch ready = new CountDownLatch(1);
        Thread listener = new Thread(() -> {
            try (Jedis jedis = pool.getResource()) {
                JedisPubSub pubSub = new JedisPubSub() {
                    @Override
                    public void onMessage(String channel, String message) {
                        //for each message recevied, it process the answer
                        //the message is a json string that contains the result of the operation
                        client.handleIncomingMessage(message);
                    }
                };
                ready.countDown();
                jedis.subscribe(pubSub, client.clientId());
            }
        });
        listener.setDaemon(true);
        listener.start();
        try {
            ready.await();
        } catch (InterruptedException ignored) {}

        //sending 3 requests to the replicas
        //the requests are AdditionOperation objects that contain the two numbers to add
        //the client will send the requests to the replicas and wait for the responses
        System.out.println("Client in ascolto su " + client.clientId());
        CountDownLatch requestLatch = new CountDownLatch(numRequests);
        for (int i = 1; i <= numRequests; i++) {
            AdditionOperation op = new AdditionOperation(i, i);
            try {
                System.out.println("wait " + intervalMs +"sec before sending the request" );
            Thread.sleep(intervalMs);
            } catch (InterruptedException ignored) {}

            ClientTicket<AdditionOperation, AdditionResult> ticket = client.sendRequest(op);
            ticket.result()
            .completeOnTimeout(null, 5, java.util.concurrent.TimeUnit.SECONDS)
            .thenAccept(res -> {
                if (res != null) {
                    System.out.println("answer to the sum: " + op.first() + " + " + op.second() + " = " + res.result());

                //try {
                    //if(!isSafe){
                    //metrics.recordRecovery(); // registra MTTR
                    //isSafe = true;
                    //}
                     //long safeTime = System.currentTimeMillis() - metrics.getSafeStartTime();
                    //metrics.writeSafeTime(safeTime);  // registra sul file il Safe Time corrente
                    //metrics.startSafePeriod();        // inizia nuovo periodo safe
               // } catch (IOException e) {e.printStackTrace();}
           // }else{
             //   isSafe = false;
             //   System.err.println("Timeout expired: system is no more safe because the quorum is not reached");
             //     try {
                      //metrics.recordFault();    // registra fine safe time
             //     } catch (IOException e) {
             //         e.printStackTrace();
             //     }
                } else {
                    System.err.println("Timeout for request " + op.first());
                }
                requestLatch.countDown();


            }).exceptionally(t -> {
                System.err.println("exception for the request" + op.first() + ": " + t);
                requestLatch.countDown(); 
                return null;
            });
        }

        try {
        requestLatch.await();
        } catch (InterruptedException ignored) {}

        System.out.println("Client terminated all requests. Exit...");
        System.exit(0);
        }

        //try {
        //    System.out.println("MTTF for this execution: " + metrics.getMTTF() + " ms");
        //    metrics.writeMTTF();
        //    System.out.println("MTTR for this execution: " + metrics.getMTTR() + " ms");
        //    metrics.writeMTTR();


        //    metrics.close();
        //} catch (IOException e) {
        //    e.printStackTrace();
        //}
    

    private static void runReplica(int replicaId, JedisPool pool, int tolerance,
                                   long timeoutMs, int replicaCount) throws IOException {
        //encoder for serialization and deserialization of messages
        AdditionReplicaEncoder encoder = new AdditionReplicaEncoder();
        NoopDigester digester = new NoopDigester();
        //transport for communication with other replicas
        AdditionReplicaTransport transport = new AdditionReplicaTransport(pool, replicaCount);
        //internal log to take track of messages
        ReplicaMessageLog log = new DefaultReplicaMessageLog(100000000, 100000000, 200000000);
        AdditionReplica replica = new AdditionReplica(
            //create the replica with the ID, the byzantine tolerance, the timeout, the log
            //other parameters and also a boolean to indicate the faulty replica
                replicaId, tolerance, timeoutMs,
                log, encoder, digester, transport,
                (replicaId == 27 )// byzantine replica is 0
                        );


        File logDir = new File("logs");
        if (!logDir.exists()) {
        logDir.mkdir();

        
}

    



        CountDownLatch ready = new CountDownLatch(1);
        //take a redis connection and subscribe to the channel replica-replicaID
        //to receive the message from other replicas
        //when a message is received, it pass it to the replica.handleIncomingMessage method
        Thread listener = new Thread(() -> {
            try (Jedis jedis = pool.getResource()) {
                JedisPubSub pubSub = new JedisPubSub() {
                    @Override
                    public void onMessage(String channel, String message) {
                            replica.handleIncomingMessage(message);
                    }
                };
                ready.countDown();
                jedis.subscribe(pubSub, "replica-" + replicaId);
            }
        });
        listener.setDaemon(true);
        listener.start();
        try {
            ready.await();
        } catch (InterruptedException ignored) {}

        //timeout management thread
        //this thread will check for timeouts and call the replica.checkTimeout method
        new Thread(() -> {
            while (true) {
                try {
                    for (ReplicaRequestKey key : replica.activeTimers()) {
                        replica.checkTimeout(key);
                    }
                    Thread.sleep(100);
                } catch (InterruptedException e) {
                    break;
                }
            }
        }).start();

        System.out.println(" Replica " + replicaId + " is listening on replica-" + replicaId);

        // Thread to send heartbeat messages every 3 seconds for AVAILABILITY
        new Thread(() -> {
            try (Jedis jedis = pool.getResource()) {
                while (true) {
                    //timestamp in seconds
                    String heartbeatMsg = "{ \"replicaId\": " + replicaId + ", \"timestamp\": " + System.currentTimeMillis() / 1000 + " }";
                    jedis.publish("heartbeat", heartbeatMsg);
                    try {
                        Thread.sleep(3000); // each 3 seconds
                    } catch (InterruptedException e) {
                        break;
                    }
                }
            }
        }).start();


    }
}
    