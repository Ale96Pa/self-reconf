/*CODICE COMMENTATO PERCHE' QUESTA E' L'AVAILABILITY MISURATA DAL CLIENT MENTRE ABBIAMO CAMBIATO POI METODO PER OTTENERE IL
DATO MISURANDOLO DALL'INTERNO DEL SISTEMA

package com.gmail.woodyc40.pbft.metrics;
import java.io.FileWriter;
import java.io.IOException;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

public class AvailabilityMetrics {
    private final List<Long> safeTimes = new ArrayList<>();
    private final List<Long> recoveryTimes = new ArrayList<>();
    private long safeStartTime;
    private long faultTime;
    private final FileWriter writer;

    public AvailabilityMetrics(String filename) throws IOException {
        this.writer = new FileWriter(filename, true); //append mode
        this.safeStartTime = System.currentTimeMillis();
    }

    // The system is considered safe -> update the start of the safe time
    public void startSafePeriod() {
        safeStartTime = System.currentTimeMillis();
    }

    //return the start of the safe time
    public long getSafeStartTime() {
        return safeStartTime;
        }

    // scrive il Safe Time corrente sul file
    public void writeSafeTime(long safeTime) throws IOException {
        safeTimes.add(safeTime);
        writer.write(Instant.now() + " , SAFE_TIME , " + safeTime + "\n");
        writer.flush();
    }

    //timeout expired -> the system is considered faulty
    public void recordFault() throws IOException {
        faultTime = System.currentTimeMillis();
        long safeTime = faultTime - safeStartTime;
        safeTimes.add(safeTime);
        writer.write(Instant.now() + ",SAFE_TIME," + safeTime + "\n");
        writer.flush();
    }

    //when the system is recovered
    public void recordRecovery() throws IOException {
        long recoveryTime = System.currentTimeMillis() - faultTime;
        recoveryTimes.add(recoveryTime);
        writer.write(Instant.now() + ", Time to recover ," + recoveryTime + "\n");
        writer.flush();

        //start a new safe period
        safeStartTime = System.currentTimeMillis();
    }

    //compute mean TTF 
    public double getMTTF() {
        return safeTimes.stream().mapToLong(Long::longValue).average().orElse(0.0);
    }

    //write mttf 
    public void writeMTTF() throws IOException {
        writer.write(Instant.now() + ", MTTF for the single execution of the sys: "+ safeTimes.stream().mapToLong(Long::longValue).average().orElse(0.0) + "\n");
        writer.flush();
    }

    //Compute mean TTR
    public double getMTTR() {
        return recoveryTimes.stream().mapToLong(Long::longValue).average().orElse(0.0);
    }

    //write mttr
    public void writeMTTR() throws IOException {
       writer.write(Instant.now() + ", MTTR for the single execution of the sys: " + recoveryTimes.stream().mapToLong(Long::longValue).average().orElse(0.0) + "\n");
       writer.flush();
    }

    public void close() throws IOException {
        writer.close();
    }

}

*/