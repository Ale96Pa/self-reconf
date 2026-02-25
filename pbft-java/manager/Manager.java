import java.util.Arrays;
import java.util.List;

class Replica {
    String name;
    String vm_id;

    Replica(String name, String vm_id) {
        this.name = name;
        this.vm_id = vm_id;
    }
}

public class Manager {

    static List<Replica> replicas = Arrays.asList(
        new Replica("replica0", "pbft-vms_linux-replica0_1756287339047_54452"),
        new Replica("replica1", "pbft-vms_linux-replica1_1756287560040_32395"),
        new Replica("replica2", "pbft-vms_linux-replica2_1756287803467_54405"),
        new Replica("replica3", "pbft-vms_linux-replica3_1756288066533_28337"),
        new Replica("replica4", "pbft-vms_linux-replica4_1756288331816_24591"),
        new Replica("replica5", "pbft-vms_linux-replica5_1756288680314_72924"),
        new Replica("replica6", "pbft-vms_linux-replica6_1756289014344_58049"),
        new Replica("replica7", "pbft-vms_linux-replica7_1756289361399_59268"),
        new Replica("replica8", "pbft-vms_linux-replica8_1756289711821_77689")
    );

    public static void main(String[] args) {
        System.out.println("The System Manager is starting the execution...");
        int counter = 0;

        while (true) {
            counter++;
            System.out.println("\n--- Monitoring cycle #" + counter + " ---");

            for (Replica r : replicas) {
                if(!isVmRunning(r)){
                    System.out.println("Replica " + r.name + " TURNED OFF.");
                }
                else if (checkCondition(r, counter)) {
                    shutdownVM(r);
                } else {
                    System.out.println("Replica " + r.name + " OK.");
                }
            }

            try {
                Thread.sleep(5000); // 5 secondi tra i cicli
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
        }
    }

    // Condizione finta: spegne replica1 al secondo ciclo
    static boolean checkCondition(Replica r, int counter) {
        return "pbft-vms_linux-replica1_1756287560040_32395".equals(r.vm_id) && counter == 2;
    }

    static void shutdownVM(Replica r) {
        System.out.println("Shutting down VM " + r.vm_id);

        String command = "VBoxManage controlvm " + r.vm_id + " poweroff";
        try {
            Process process = Runtime.getRuntime().exec(command);
            process.waitFor();
            System.out.println("VM " + r.vm_id + " has been shut down.");
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    static boolean isVmRunning(Replica r) {
        String command = "VBoxManage showvminfo " + r.vm_id + " --machinereadable";
        try {
            Process process = Runtime.getRuntime().exec(command);
            java.io.BufferedReader reader = new java.io.BufferedReader(
                new java.io.InputStreamReader(process.getInputStream())
            );
            String line;
            while ((line = reader.readLine()) != null) {
                if (line.startsWith("VMState=") && line.contains("running")) {
                    return true;
                }
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
        return false;
    }
}